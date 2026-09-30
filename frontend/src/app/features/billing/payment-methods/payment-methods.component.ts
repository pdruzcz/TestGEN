import { Component, OnInit, inject, signal } from "@angular/core";
import { MatButton } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatChip, MatChipSet } from "@angular/material/chips";
import { MatIcon } from "@angular/material/icon";
import { RouterLink } from "@angular/router";

import { FlutterBridgeService } from "../../../shared/services/flutter-bridge.service";
import {
  BillingService,
  PaymentMethod,
  PaymentMethodKind,
} from "../billing.service";

/** Klucz sessionStorage — identyfikator rejestracji dla strony powrotu (polling). */
export const PAYMENT_METHOD_REGISTRATION_KEY = "tg_payment_method_id";

/**
 * Metody płatności (Story 7.2, AC2/AC3) — lista kart i aliasów BLIK,
 * dodanie karty (rejestracja bez obciążenia → redirect tpay) i usuwanie.
 * Banner past_due (AC6) informuje Ownera o problemie z odnowieniem.
 * Pełny portal bilingowy — Story 7.7.
 */
@Component({
  selector: "app-payment-methods",
  imports: [MatCardModule, MatButton, MatChipSet, MatChip, MatIcon, RouterLink],
  templateUrl: "./payment-methods.component.html",
  styleUrl: "./payment-methods.component.scss",
  providers: [BillingService],
})
export class PaymentMethodsComponent implements OnInit {
  private readonly billing = inject(BillingService);
  private readonly flutter = inject(FlutterBridgeService);

  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly actionError = signal<string | null>(null);
  readonly methods = signal<PaymentMethod[]>([]);
  readonly pastDue = signal(false);

  ngOnInit(): void {
    this.billing.getPaymentMethods().subscribe({
      next: (methods) => {
        this.methods.set(methods.filter((m) => m.tpayStatus !== "deleted"));
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.listErrorMessage(err?.status));
        this.loading.set(false);
      },
    });
    this.billing.getSubscription().subscribe({
      next: (sub) => this.pastDue.set(sub.status === "past_due"),
      error: () => this.pastDue.set(false),
    });
  }

  /** AC2 — dodaj kartę: rejestracja u tpay (bez obciążenia), redirect na panel. */
  addCard(): void {
    this.actionError.set(null);
    this.billing.addPaymentMethod().subscribe({
      next: (registration) => {
        sessionStorage.setItem(
          PAYMENT_METHOD_REGISTRATION_KEY,
          registration.tokenId,
        );
        this.openRegistrationUrl(registration.registrationUrl);
      },
      error: (err) => this.actionError.set(this.listErrorMessage(err?.status)),
    });
  }

  /** AC3 — usunięcie metody; 409 = ostatnia metoda aktywnej subskrypcji. */
  remove(method: PaymentMethod): void {
    this.actionError.set(null);
    this.billing.deletePaymentMethod(method.id).subscribe({
      next: () =>
        this.methods.update((list) => list.filter((m) => m.id !== method.id)),
      error: (err) => {
        if (err?.status === 409) {
          this.actionError.set(
            "To jedyna aktywna metoda płatności subskrypcji cyklicznej — najpierw dodaj inną metodę.",
          );
          return;
        }
        this.actionError.set(
          "Nie udało się usunąć metody płatności. Spróbuj ponownie za chwilę.",
        );
      },
    });
  }

  kindLabel(kind: PaymentMethodKind): string {
    return kind === "card_token" ? "Karta" : "BLIK";
  }

  methodIcon(kind: PaymentMethodKind): string {
    return kind === "card_token" ? "credit_card" : "contactless";
  }

  methodTitle(method: PaymentMethod): string {
    if (method.kind === "card_token") {
      const brand = (method.cardBrand ?? "").toUpperCase() || "KARTA";
      return method.cardTail ? `${brand} •••• ${method.cardTail}` : brand;
    }
    return "Płatności Powtarzalne";
  }

  methodSubtitle(method: PaymentMethod): string {
    return method.kind === "card_token"
      ? "Zapisana przy płatności — odnowienia bez udziału użytkownika"
      : "Alias zapisany przy pierwszej płatności BLIK";
  }

  statusLabel(method: PaymentMethod): string {
    switch (method.tpayStatus) {
      case "active":
        return "Aktywna";
      case "pending":
        return "W trakcie rejestracji";
      case "suspended":
        return "Zawieszona";
      default:
        return method.tpayStatus;
    }
  }

  /** Flutter WebView: zewnętrzna przeglądarka (wymogi tpay/3DS), web: redirect. */
  private openRegistrationUrl(url: string): void {
    if (this.flutter.isFlutterEnvironment()) {
      this.flutter.openExternal(url);
      return;
    }
    this.redirectTo(url);
  }

  /** Redirect w web app (publiczny: jsdom w testach nie nawiguje — spy). */
  redirectTo(url: string): void {
    window.location.href = url;
  }

  private listErrorMessage(status: number | undefined): string {
    if (status === 403) {
      return "Tylko administrator konta (Owner) może zarządzać metodami płatności.";
    }
    return "Nie udało się pobrać metod płatności. Spróbuj ponownie za chwilę.";
  }
}
