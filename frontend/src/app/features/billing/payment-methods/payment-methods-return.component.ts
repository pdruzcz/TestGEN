import { Component, OnDestroy, OnInit, inject, signal } from "@angular/core";
import { MatButton } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { RouterLink } from "@angular/router";
import { Subscription, timer } from "rxjs";

import { BillingService } from "../billing.service";
import { PAYMENT_METHOD_REGISTRATION_KEY } from "./payment-methods.component";

/** Polling statusu rejestracji: 5 prób co 3 s (notyfikacja tpay zwykle < 15 s). */
const POLL_ATTEMPTS = 5;
const POLL_INTERVAL_MS = 3000;

type ReturnState = "polling" | "confirmed" | "pending" | "missing";

/**
 * Powrót z rejestracji karty u tpay (Story 7.2, AC2) — callbackUrl rejestracji.
 *
 * Notyfikacja ``data.token`` może dotrzeć po powrocie płatnika, dlatego
 * strona pollinguje listę metod do momentu potwierdzenia (pending→confirmed)
 * i pokazuje stan rejestracji — współdzielony wzorzec stron powrotu z 7.4.
 */
@Component({
  selector: "app-payment-methods-return",
  imports: [MatCardModule, MatButton, MatProgressSpinnerModule, RouterLink],
  templateUrl: "./payment-methods-return.component.html",
  styleUrl: "./payment-methods-return.component.scss",
  providers: [BillingService],
})
export class PaymentMethodsReturnComponent implements OnInit, OnDestroy {
  private readonly billing = inject(BillingService);
  private pollSubscription: Subscription | null = null;

  readonly state = signal<ReturnState>("polling");

  ngOnInit(): void {
    const tokenId = sessionStorage.getItem(PAYMENT_METHOD_REGISTRATION_KEY);
    if (!tokenId) {
      this.state.set("missing");
      return;
    }

    let attempt = 0;
    this.pollSubscription = timer(0, POLL_INTERVAL_MS).subscribe(() => {
      attempt += 1;
      this.billing.getPaymentMethods().subscribe({
        next: (methods) => {
          const token = methods.find((m) => m.id === tokenId);
          if (token && token.tpayStatus === "active") {
            sessionStorage.removeItem(PAYMENT_METHOD_REGISTRATION_KEY);
            this.state.set("confirmed");
            this.stopPolling();
          } else if (attempt >= POLL_ATTEMPTS) {
            this.state.set("pending");
            this.stopPolling();
          }
        },
        error: () => {
          if (attempt >= POLL_ATTEMPTS) {
            this.state.set("pending");
            this.stopPolling();
          }
        },
      });
    });
  }

  ngOnDestroy(): void {
    this.stopPolling();
  }

  private stopPolling(): void {
    this.pollSubscription?.unsubscribe();
    this.pollSubscription = null;
  }
}
