import { Component, OnInit, computed, inject, signal } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatDialog } from "@angular/material/dialog";
import { MatIcon } from "@angular/material/icon";
import { RouterLink } from "@angular/router";

import { BillingService, SubscriptionDetail } from "../../billing.service";
import { CancelConfirmDialogComponent } from "../cancel-confirm-dialog/cancel-confirm-dialog.component";

/**
 * Szczegóły subskrypcji (Story 7.7, AC3) — plan, status, okres rozliczeniowy,
 * metoda płatności i zaplanowany downgrade (7.5). Akcje: anulowanie z dialogiem
 * potwierdzenia (AC4), reaktywacja (AC5), zmiana planu / metody płatności.
 */
@Component({
  selector: "app-subscription-detail",
  imports: [MatCardModule, MatButtonModule, MatIcon, RouterLink],
  templateUrl: "./subscription-detail.component.html",
  styleUrl: "./subscription-detail.component.scss",
  providers: [BillingService],
})
export class SubscriptionDetailComponent implements OnInit {
  private readonly billing = inject(BillingService);
  private readonly dialog = inject(MatDialog);

  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly actionError = signal<string | null>(null);
  readonly actionInfo = signal<string | null>(null);
  readonly detail = signal<SubscriptionDetail | null>(null);

  /** AC3 — plan płatny (Basic/Premium) podlega anulowaniu; Freemium nie. */
  readonly isPaidPlan = computed(() => {
    const plan = this.detail()?.planName;
    return plan === "basic" || plan === "premium";
  });

  /** AC4/AC5 — anulowana (flaga) → pokaż „Reaktywuj" zamiast „Anuluj". */
  readonly isCancelled = computed(
    () => this.detail()?.cancelAtPeriodEnd === true,
  );

  readonly hasPendingChange = computed(
    () => this.detail()?.pendingChange !== null,
  );

  ngOnInit(): void {
    this.billing.getSubscription().subscribe({
      next: (detail) => {
        this.detail.set(detail);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.loadErrorMessage(err?.status));
        this.loading.set(false);
      },
    });
  }

  /** AC4 — dialog potwierdzenia anulowania; wynik = odświeżony detail. */
  openCancelDialog(): void {
    const current = this.detail();
    if (current === null) {
      return;
    }
    this.actionError.set(null);
    this.actionInfo.set(null);
    this.dialog
      .open(CancelConfirmDialogComponent, { data: current, width: "560px" })
      .afterClosed()
      .subscribe((result) => {
        if (result) {
          this.detail.set(result);
          this.actionInfo.set(
            `Subskrypcja ${this.planLabel(result)} aktywna do ${this.dateLabel(result.currentPeriodEnd)}.`,
          );
        }
      });
  }

  /** AC5 — reaktywacja: zdjęcie flagi, powrót harmonogramu obciążeń. */
  reactivate(): void {
    this.actionError.set(null);
    this.actionInfo.set(null);
    this.billing.reactivateSubscription().subscribe({
      next: (detail) => {
        this.detail.set(detail);
        this.actionInfo.set(
          `Subskrypcja ${this.planLabel(detail)} jest aktywna.`,
        );
      },
      error: (err) =>
        this.actionError.set(
          this.actionErrorMessage(err?.status, err?.error?.detail),
        ),
    });
  }

  planLabel(detail: SubscriptionDetail): string {
    return detail.planDisplayName ?? "subskrypcji";
  }

  /** AC3 — metoda płatności: karta (brand + ogon) albo BLIK. */
  paymentMethodLabel(detail: SubscriptionDetail): string {
    const method = detail.paymentMethod;
    if (method === null) {
      return "Brak zapisanej metody";
    }
    if (method.kind === "card_token") {
      const brand = (method.cardBrand ?? "").toUpperCase() || "KARTA";
      return method.cardTail ? `${brand} •••• ${method.cardTail}` : brand;
    }
    return "BLIK (Płatności Powtarzalne)";
  }

  statusLabel(detail: SubscriptionDetail): string {
    switch (detail.status) {
      case "active":
        return "Aktywna";
      case "past_due":
        return "Windykacja";
      case "canceled":
        return "Anulowana";
      case "incomplete":
        return "Niekompletna";
      default:
        return detail.status;
    }
  }

  /** Kwota miesięczna — „50,00 zł / mies." (backend wysyła „50.00"/„PLN"). */
  priceLabel(detail: SubscriptionDetail): string {
    if (detail.planPriceMonthly === null) {
      return "—";
    }
    const price = detail.planPriceMonthly.replace(".", ",");
    const currency = detail.planCurrency === "PLN" ? "zł" : detail.planCurrency;
    return `${price} ${currency} / mies.`;
  }

  dateLabel(value: string | null): string {
    if (value === null) {
      return "—";
    }
    return new Date(value).toLocaleDateString("pl-PL");
  }

  private loadErrorMessage(status: number | undefined): string {
    if (status === 404) {
      return "Brak subskrypcji dla tego konta.";
    }
    return "Nie udało się pobrać danych subskrypcji. Spróbuj ponownie za chwilę.";
  }

  private actionErrorMessage(
    status: number | undefined,
    detail: string | null,
  ): string {
    if (status === 403) {
      return "Tylko administrator konta (Owner) może zarządzać subskrypcją.";
    }
    return detail ?? "Operacja nie powiodła się. Spróbuj ponownie za chwilę.";
  }
}
