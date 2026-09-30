import { Component, computed, inject, input } from "@angular/core";
import { RouterLink } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import {
  ModuleLocksService,
  PLAN_LABELS,
  PlanName,
} from "../../../core/services/module-locks.service";

/**
 * Treść zakładki zablokowanego modułu (Story 7.13) — banner inline
 * „dostępne w planie X" + panel upsell z CTA. Zakładka pozostaje widoczna
 * (widoczne-zablokowane); po upgrade blokady znikają bez reloadu
 * (signal z ModuleLocksService).
 */
@Component({
  selector: "app-locked-module",
  standalone: true,
  imports: [RouterLink, MatButtonModule, MatIconModule],
  template: `
    <div
      class="locked-module-banner"
      role="status"
      data-testid="locked-module-banner"
    >
      <mat-icon aria-hidden="true">lock</mat-icon>
      <p class="locked-module-banner__message">{{ bannerText() }}</p>
      <a
        mat-flat-button
        color="primary"
        routerLink="/billing/plans"
        data-testid="locked-module-cta"
      >
        Zobacz plany
      </a>
    </div>
    <div class="locked-module-panel" data-testid="locked-module-panel">
      <mat-icon aria-hidden="true" class="locked-module-panel__icon"
        >lock</mat-icon
      >
      <h2 class="locked-module-panel__title">{{ title() }}</h2>
      <p class="locked-module-panel__desc">{{ description() }}</p>
      <a mat-flat-button color="primary" routerLink="/billing/plans"
        >Ulepsz plan</a
      >
    </div>
  `,
  styles: [
    `
      .locked-module-banner {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 16px;
        background: #fff8e1;
        color: #795548;
        border: 1px solid #ffe082;
        border-radius: 8px;
      }

      .locked-module-banner__message {
        margin: 0;
        flex: 1;
      }

      .locked-module-panel {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 12px;
        padding: 48px 24px;
        margin-top: 16px;
        background: #eceff1;
        border-radius: 12px;
        text-align: center;
      }

      .locked-module-panel__icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        color: #90a4ae;
      }

      .locked-module-panel__title {
        margin: 0;
        font-size: 18px;
        font-weight: 600;
        color: #546e7a;
      }

      .locked-module-panel__desc {
        margin: 0;
        max-width: 560px;
        color: #78909c;
        line-height: 1.5;
      }
    `,
  ],
})
export class LockedModuleComponent {
  private readonly moduleLocks = inject(ModuleLocksService);

  /** Klucz modułu gated (np. „security") — dla wymaganego planu. */
  readonly moduleKey = input.required<string>();

  /** Nazwa modułu pokazywana w panelu (PL). */
  readonly title = input.required<string>();

  /** Opis zastosowania modułu (PL) — wymóg wniosku FEPW. */
  readonly description = input.required<string>();

  protected readonly requiredPlan = computed<PlanName>(
    () => this.moduleLocks.requiredPlanOf(this.moduleKey()) ?? "premium",
  );

  protected readonly bannerText = computed(
    () =>
      `Funkcja dostępna w planie ${PLAN_LABELS[this.requiredPlan()]} — ` +
      "ulepsz subskrypcję, aby ją odblokować.",
  );
}
