import { Component, computed, inject, signal } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import {
  MAT_DIALOG_DATA,
  MatDialogModule,
  MatDialogRef,
} from "@angular/material/dialog";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";

import {
  BillingService,
  Plan,
  PlanChangeResult,
  Proration,
} from "../../billing.service";

export interface PlanChangeConfirmData {
  /** Plan docelowy. */
  targetPlan: Plan;
  /** Aktualny plan tenanta. */
  currentPlan: Plan;
}

/**
 * Dialog potwierdzenia zmiany planu (Story 7.5, AC5/AC7).
 *
 * Pobiera lokalny podgląd proration z backendu (AC5 — kwota identyczna
 * z późniejszym obciążeniem), pokazuje ostrzeżenia przy downgrade
 * (utracone funkcje, data efektywna) i po „Potwierdź" woła
 * POST /billing/subscription/change. Zamyka się z `PlanChangeResult` —
 * redirect na checkout tpay (paymentUrl) wykonuje komponent rodzica.
 */
@Component({
  selector: "app-plan-change-confirm",
  standalone: true,
  imports: [MatButtonModule, MatDialogModule, MatProgressSpinnerModule],
  templateUrl: "./plan-change-confirm.component.html",
  providers: [BillingService],
})
export class PlanChangeConfirmComponent {
  private readonly billing = inject(BillingService);
  private readonly dialogRef =
    inject<MatDialogRef<PlanChangeConfirmComponent, PlanChangeResult>>(
      MatDialogRef,
    );
  readonly data = inject<PlanChangeConfirmData>(MAT_DIALOG_DATA);

  readonly loading = signal(true);
  readonly submitting = signal(false);
  readonly error = signal<string | null>(null);
  readonly proration = signal<Proration | null>(null);

  readonly isDowngrade = computed(
    () => this.proration()?.changeType === "downgrade",
  );

  /** Funkcje tracone przy downgrade — porównanie macierzy `features`. */
  readonly lostFeatures = computed<string[]>(() => {
    if (!this.isDowngrade()) return [];
    const current = this.data.currentPlan.features;
    const target = this.data.targetPlan.features;
    const lost: string[] = [];
    const numeric: [string, string][] = [
      ["analyses", "Mniej analiz miesięcznie"],
      ["testCases", "Mniej przypadków testowych"],
      ["storageBytes", "Mniejszy storage"],
      ["filesPerAnalysis", "Mniej plików na analizę"],
      ["rateLimitPerMin", "Niższy rate limit"],
    ];
    for (const [key, label] of numeric) {
      const cur = current[key];
      const tgt = target[key];
      // null = bez limitu; liczba < liczba lub liczba zamiast null = strata
      if (cur === null && tgt !== null) lost.push(label);
      else if (
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
  });

  constructor() {
    this.billing.getProration(this.data.targetPlan.name).subscribe({
      next: (proration) => {
        this.proration.set(proration);
        this.loading.set(false);
      },
      error: () => {
        this.error.set("Nie udało się wyliczyć kwoty zmiany planu.");
        this.loading.set(false);
      },
    });
  }

  confirm(): void {
    this.submitting.set(true);
    this.error.set(null);
    this.billing.changePlan(this.data.targetPlan.name).subscribe({
      next: (result) => this.dialogRef.close(result),
      error: (err) => {
        this.submitting.set(false);
        this.error.set(
          err?.error?.detail ??
            "Zmiana planu nie powiodła się. Spróbuj ponownie.",
        );
      },
    });
  }

  cancel(): void {
    this.dialogRef.close();
  }
}
