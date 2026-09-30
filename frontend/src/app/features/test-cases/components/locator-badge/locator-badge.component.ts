import { Component, computed, input } from "@angular/core";
import { MatIconModule } from "@angular/material/icon";

import {
  LOCATOR_STRATEGY_LABEL,
  detectLocatorStrategy,
  isUiFramework,
  type LocatorStrategy,
} from "../../utils/locator-strategy";

/**
 * Story 1.51-zakańczenie + Story 6.5 — a read-only badge showing the locator
 * strategy of a UI test case, inferred from its ``testCode``. Mirrors the
 * self-healing locator ladder. Renders nothing for non-UI frameworks or tests
 * without a recognised locator.
 */
@Component({
  selector: "app-locator-badge",
  standalone: true,
  imports: [MatIconModule],
  template: `
    @if (strategy(); as s) {
      <span class="loc-badge" [attr.data-strategy]="s">
        <mat-icon aria-hidden="true">gps_fixed</mat-icon>
        {{ label(s) }}
      </span>
    }
  `,
  styles: [
    `
      :host {
        display: inline-flex;
      }
      .loc-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 500;
        background: #eef2ff;
        color: #3730a3;
        white-space: nowrap;
      }
      .loc-badge mat-icon {
        font-size: 14px;
        height: 14px;
        width: 14px;
      }
    `,
  ],
})
export class LocatorBadgeComponent {
  readonly testCode = input<string | null>(null);
  readonly framework = input<string | null>(null);

  readonly strategy = computed<LocatorStrategy | null>(() =>
    isUiFramework(this.framework())
      ? detectLocatorStrategy(this.testCode())
      : null,
  );

  label(strategy: LocatorStrategy): string {
    return LOCATOR_STRATEGY_LABEL[strategy] ?? strategy;
  }
}
