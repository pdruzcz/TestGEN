import { Component, computed, inject } from "@angular/core";
import { RouterLink } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { QuotaAlertService } from "../../interceptors/quota-interceptor";

/** Polskie etykiety zasobów do komunikatu AC6. */
const RESOURCE_LABELS: Record<string, string> = {
  analyses: "analiz",
  test_cases: "przypadków testowych",
  storage_bytes: "przestrzeni dyskowej",
  files_per_analysis: "plików na analizę",
};

const PLAN_LABELS: Record<string, string> = {
  freemium: "Freemium",
  basic: "Basic",
  premium: "Premium",
};

/**
 * Inline alert po 429 `limit_reached` (Story 7.8, AC6) — komunikat
 * o przekroczonym limicie + CTA "Uaktualnij plan" → /billing/plans.
 */
@Component({
  selector: "app-quota-exceeded-banner",
  imports: [RouterLink, MatButtonModule, MatIconModule],
  templateUrl: "./quota-exceeded-banner.component.html",
  styles: [
    `
      .quota-banner {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        z-index: 1100;
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 16px;
        background: #fff3e0;
        color: #5d4037;
        border-bottom: 1px solid #ffb74d;
      }

      .quota-banner__message {
        flex: 1;
      }

      .quota-banner__close {
        margin-left: auto;
      }
    `,
  ],
})
export class QuotaExceededBannerComponent {
  protected readonly alerts = inject(QuotaAlertService);

  /** Komunikat AC6: "Osiągnąłeś limit {resource} w planie {plan}. …" */
  protected readonly message = computed(() => {
    const alert = this.alerts.alert();
    if (!alert) {
      return "";
    }
    const resource = RESOURCE_LABELS[alert.resource] ?? alert.resource;
    const plan = PLAN_LABELS[alert.plan] ?? alert.plan;
    return (
      `Osiągnąłeś limit ${resource} w planie ${plan}. ` +
      "Uaktualnij plan, aby uzyskać wyższe limity."
    );
  });

  protected dismiss(): void {
    this.alerts.dismiss();
  }
}
