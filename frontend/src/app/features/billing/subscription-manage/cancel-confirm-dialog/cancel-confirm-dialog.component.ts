import { Component, computed, inject, signal } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import {
  MAT_DIALOG_DATA,
  MatDialogModule,
  MatDialogRef,
} from "@angular/material/dialog";
import { MatIcon } from "@angular/material/icon";

import { BillingService, SubscriptionDetail } from "../../billing.service";

/**
 * Dialog potwierdzenia anulowania subskrypcji (Story 7.7, AC4).
 *
 * Informuje o dacie wygaśnięcia (koniec bieżącego okresu), automatycznym
 * powrocie do planu Freemium (lub niższego — gdy downgrade był zaplanowany
 * przez 7.5) i liście traconych funkcji (macierz `features` planów).
 * Po „Potwierdź" woła POST /billing/subscription/cancel — operacja lokalna
 * (§3.5 planu tpay), zamyka się z odświeżonym `SubscriptionDetail`.
 */
@Component({
  selector: "app-cancel-confirm-dialog",
  imports: [MatButtonModule, MatDialogModule, MatIcon],
  templateUrl: "./cancel-confirm-dialog.component.html",
  styleUrl: "./cancel-confirm-dialog.component.scss",
  providers: [BillingService],
})
export class CancelConfirmDialogComponent {
  private readonly billing = inject(BillingService);
  private readonly dialogRef =
    inject<MatDialogRef<CancelConfirmDialogComponent, SubscriptionDetail>>(
      MatDialogRef,
    );
  readonly data = inject<SubscriptionDetail>(MAT_DIALOG_DATA);

  readonly submitting = signal(false);
  readonly error = signal<string | null>(null);

  /** Plan po wygaśnięciu: docelowy zaplanowanego downgrade'u (7.5) albo Freemium. */
  readonly effectivePlan = computed(
    () => this.data.pendingChange?.toPlan ?? "freemium",
  );

  readonly expiryDate = computed(() =>
    new Date(this.data.currentPeriodEnd).toLocaleDateString("pl-PL"),
  );

  /** AC4 — utracone funkcje względem planu docelowego (macierz z GET /plans). */
  readonly lostFeatures = signal<string[]>([]);

  constructor() {
    this.billing.getPlans().subscribe({
      next: (comparison) => {
        const current = comparison.plans.find(
          (p) => p.name === this.data.planName,
        );
        const target = comparison.plans.find(
          (p) => p.name === this.effectivePlan(),
        );
        if (current && target) {
          this.lostFeatures.set(
            this.diffFeatures(current.features, target.features),
          );
        }
      },
      error: () => this.lostFeatures.set([]), // lista opcjonalna — dialog działa bez niej
    });
  }

  confirm(): void {
    this.submitting.set(true);
    this.error.set(null);
    this.billing.cancelSubscription().subscribe({
      next: (detail) => this.dialogRef.close(detail),
      error: (err) => {
        this.submitting.set(false);
        this.error.set(
          err?.error?.detail ??
            "Anulowanie subskrypcji nie powiodło się. Spróbuj ponownie.",
        );
      },
    });
  }

  cancel(): void {
    this.dialogRef.close();
  }

  /** Różnica limitów planu — te same etykiety co dialog zmiany planu (7.5). */
  private diffFeatures(
    current: Record<string, unknown>,
    target: Record<string, unknown>,
  ): string[] {
    const lost: string[] = [];
    const numeric: [string, string][] = [
      ["analyses", "Mniej analiz miesięcznie"],
      ["testCases", "Mniej przypadków testowych"],
      ["storageBytes", "Mniejszy limit miejsca"],
      ["filesPerAnalysis", "Mniej plików na analizę"],
      ["rateLimitPerMin", "Niższy limit zapytań"],
    ];
    for (const [key, label] of numeric) {
      const cur = current[key];
      const tgt = target[key];
      // null = bez limitu; liczba < liczba lub liczba zamiast null = strata
      if (cur === null && tgt !== null) {
        lost.push(label);
      } else if (
        typeof cur === "number" &&
        typeof tgt === "number" &&
        tgt < cur
      ) {
        lost.push(label);
      }
    }
    if (current["prioritySupport"] && !target["prioritySupport"]) {
      lost.push("Brak priorytetowego wsparcia");
    }
    return lost;
  }
}
