import { Component, computed, inject } from "@angular/core";
import { RouterLink } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { FeatureLockAlertService } from "../../interceptors/feature-lock-interceptor";
import { PLAN_LABELS } from "../../../core/services/module-locks.service";

/**
 * Inline alert po 402 `feature_requires_plan` (Story 7.13) — komunikat
 * „funkcja dostępna w planie X" + CTA „Zobacz plany" → /billing/plans.
 * Wzorzec QuotaExceededBannerComponent (7.8).
 */
@Component({
  selector: "app-feature-locked-banner",
  standalone: true,
  imports: [RouterLink, MatButtonModule, MatIconModule],
  templateUrl: "./feature-locked-banner.component.html",
  styles: [
    `
      .feature-banner {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        z-index: 1100;
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 16px;
        background: #fff8e1;
        color: #795548;
        border-bottom: 1px solid #ffe082;
      }

      .feature-banner__message {
        flex: 1;
      }
    `,
  ],
})
export class FeatureLockedBannerComponent {
  protected readonly alerts = inject(FeatureLockAlertService);

  /** Komunikat PL: „Funkcja dostępna w planie {plan}. Ulepsz…" */
  protected readonly message = computed(() => {
    const alert = this.alerts.alert();
    if (!alert) {
      return "";
    }
    const plan = PLAN_LABELS[alert.requiredPlan] ?? alert.requiredPlan;
    return (
      `Funkcja dostępna w planie ${plan}. ` +
      "Ulepsz subskrypcję, aby korzystać z tego modułu."
    );
  });

  protected dismiss(): void {
    this.alerts.dismiss();
  }
}
