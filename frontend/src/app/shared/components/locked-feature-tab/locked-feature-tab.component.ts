import { Component, computed, inject, input } from "@angular/core";
import { Router } from "@angular/router";
import { MatIconModule } from "@angular/material/icon";
import { MatTooltipModule } from "@angular/material/tooltip";
import {
  PLAN_LABELS,
  PlanName,
} from "../../../core/services/module-locks.service";

/**
 * Wzorzec „widoczne-zablokowane" (Story 7.13 / FR71, wniosek FEPW) —
 * opakowanie zakładki/przycisku modułu gated.
 *
 * WCAG 2.1 AA (NFR25-29):
 * - komunikat nie tylko na hover — matTooltip pokazuje się też na `focus`,
 *   a `aria-label` ogłasza treść screen readerowi;
 * - zablokowana kontrolka focusable, ale nieaktywna (`aria-disabled`,
 *   `tabindex=0`; klik/Enter = CTA → /billing/plans, nie akcja modułu);
 * - stan locked rozpoznawalny nie tylko kolorem — ikona kłódki + tekst
 *   z nazwą wymaganego planu.
 */
@Component({
  selector: "app-locked-feature-tab",
  standalone: true,
  imports: [MatIconModule, MatTooltipModule],
  template: `
    <span
      class="locked-feature-tab"
      [class.locked-feature-tab--locked]="locked()"
      [attr.role]="locked() ? 'button' : null"
      [attr.aria-disabled]="locked() ? 'true' : null"
      [attr.tabindex]="locked() ? 0 : null"
      [attr.aria-label]="locked() ? tooltipText() : null"
      [matTooltip]="tooltipText()"
      [matTooltipDisabled]="!locked()"
      (click)="activate()"
      (keydown.enter)="activate()"
      (keydown.space)="activate()"
    >
      <ng-content />
      @if (locked()) {
        <mat-icon
          aria-hidden="true"
          class="locked-feature-tab__lock"
          data-testid="locked-feature-lock"
          >lock</mat-icon
        >
      }
    </span>
  `,
  styles: [
    `
      .locked-feature-tab {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        outline: none;
      }

      .locked-feature-tab--locked {
        color: #78909c;
        cursor: pointer;
      }

      .locked-feature-tab--locked:focus-visible {
        outline: 2px solid #1976d2;
        outline-offset: 2px;
        border-radius: 4px;
      }

      .locked-feature-tab__lock {
        font-size: 14px;
        width: 14px;
        height: 14px;
        color: #90a4ae;
      }
    `,
  ],
})
export class LockedFeatureTabComponent {
  private readonly router = inject(Router);

  /** Czy moduł jest zablokowany dla planu tenanta. */
  readonly locked = input(false);

  /** Wymagany plan z konfiguracji modułu (null → moduł niegated). */
  readonly requiredPlan = input<PlanName | null>(null);

  /** Komunikat PL z dynamiczną nazwą wymaganego planu (nie hardcoded). */
  protected readonly tooltipText = computed(() => {
    if (!this.locked()) {
      return "";
    }
    const plan = PLAN_LABELS[this.requiredPlan() ?? "basic"] ?? "Basic";
    return `Funkcja dostępna w planie ${plan}. Kliknij, aby zobaczyć plany subskrypcji.`;
  });

  /** CTA — klik/Enter na zablokowanym module prowadzi do strony planów. */
  protected activate(): void {
    if (this.locked()) {
      void this.router.navigate(["/billing/plans"]);
    }
  }
}
