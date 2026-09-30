import { Component, computed, inject, signal } from "@angular/core";
import { MatButton } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatDialog } from "@angular/material/dialog";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { RouterLink } from "@angular/router";

import {
  PlanChangeConfirmComponent,
  PlanChangeConfirmData,
} from "../subscription-manage/plan-change-confirm/plan-change-confirm.component";
import { BillingService, Plan, PlanName } from "../billing.service";
import { ModuleLocksService } from "../../../core/services/module-locks.service";

/** Hierarchia planów (7.5) — Freemium < Basic < Premium. */
const PLAN_RANK: Record<PlanName, number> = {
  freemium: 0,
  basic: 1,
  premium: 2,
};

interface ComparisonRow {
  label: string;
  /** Wartość per plan (kolejność: freemium, basic, premium). */
  values: string[];
}

@Component({
  selector: "app-plan-comparison",
  imports: [MatCardModule, MatButton, MatProgressSpinnerModule, RouterLink],
  templateUrl: "./plan-comparison.component.html",
  styleUrl: "./plan-comparison.component.scss",
  providers: [BillingService],
})
export class PlanComparisonComponent {
  private readonly billing = inject(BillingService);
  private readonly dialog = inject(MatDialog);

  /** Story 7.13 — reaktywny unlock blokad modułów po zmianie planu. */
  private readonly moduleLocks = inject(ModuleLocksService);

  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly plans = signal<Plan[]>([]);
  readonly currentPlan = signal<PlanName | null>(null);
  readonly termsUrl = signal("https://test-gen.pl/regulamin/");
  readonly privacyPolicyUrl = signal("https://test-gen.pl/polityka/");

  /** Wiersze macierzy wyliczane z `features` — jedno źródło prawdy. */
  readonly comparisonRows = computed<ComparisonRow[]>(() => {
    const byName = new Map(this.plans().map((p) => [p.name, p]));
    const order: PlanName[] = ["freemium", "basic", "premium"];
    const get = (key: string): string[] =>
      order.map((name) => {
        const plan = byName.get(name);
        return plan ? this.formatFeature(plan.features[key]) : "—";
      });

    return [
      { label: "Analizy / mies.", values: get("analyses") },
      { label: "Przypadki testowe", values: get("testCases") },
      { label: "Storage", values: get("storageBytes") },
      { label: "Pliki na analizę", values: get("filesPerAnalysis") },
      {
        label: "Użytkownicy",
        values: ["Bez limitu", "Bez limitu", "Bez limitu"],
      },
      { label: "Rate limiting (req/min)", values: get("rateLimitPerMin") },
      { label: "Priorytetowe wsparcie", values: get("prioritySupport") },
    ];
  });

  constructor() {
    this.loadPlans();
  }

  private loadPlans(): void {
    this.billing.getPlans().subscribe({
      next: (comparison) => {
        this.plans.set(comparison.plans);
        this.currentPlan.set(comparison.currentPlan);
        this.termsUrl.set(comparison.termsUrl);
        this.privacyPolicyUrl.set(comparison.privacyPolicyUrl);
        this.loading.set(false);
      },
      error: () => {
        this.error.set(
          "Nie udało się pobrać planów subskrypcji. Spróbuj ponownie.",
        );
        this.loading.set(false);
      },
    });
  }

  isCurrent(name: PlanName): boolean {
    return this.currentPlan() === name;
  }

  isPaid(name: PlanName): boolean {
    return name === "basic" || name === "premium";
  }

  /** 7.5 AC7: zmiana planu (dialog) — tylko gdy tenant ma już plan płatny.
   * Z Freemium zakup idzie ścieżką checkoutu 7.4 (routerLink). */
  isPlanChange(name: PlanName): boolean {
    const current = this.currentPlan();
    return current !== null && current !== "freemium" && current !== name;
  }

  /** Dynamiczna etykieta przycisku wg hierarchii planów (AC7). */
  changeCtaLabel(plan: Plan): string {
    const current = this.currentPlan();
    if (current && PLAN_RANK[plan.name] > PLAN_RANK[current]) {
      return `Przejdź na ${plan.displayName}`;
    }
    return `Obniż do ${plan.displayName}`;
  }

  /** Otwiera dialog potwierdzenia z podglądem proration (AC5/AC7). */
  openChangeDialog(target: Plan): void {
    const current = this.plans().find((p) => p.name === this.currentPlan());
    if (!current) return;
    const data: PlanChangeConfirmData = {
      targetPlan: target,
      currentPlan: current,
    };
    this.dialog
      .open(PlanChangeConfirmComponent, { data, width: "480px" })
      .afterClosed()
      .subscribe((result) => {
        if (!result) return;
        if (result.paymentUrl) {
          // Upgrade bez zapisanej metody — dokończenie płatności u tpay.
          window.location.href = result.paymentUrl;
          return;
        }
        this.loadPlans(); // downgrade zaplanowany / upgrade bez obciążenia
        this.moduleLocks.refresh(); // 7.13: blokady modułów aktualizują się bez reloadu
      });
  }

  /** CTA dla planu płatnego kieruje do checkout (7.4). */
  ctaRouterLink(name: PlanName): string[] {
    return ["/billing/checkout"];
  }

  ctaQueryParams(name: PlanName): Record<string, string> {
    return { plan: name };
  }

  /** Skrócona lista 3 cech na karcie planu. */
  cardHighlights(plan: Plan): string[] {
    const f = plan.features;
    return [
      `${this.formatFeature(f["analyses"])} analiz / mies.`,
      `${this.formatFeature(f["testCases"])} przypadków testowych`,
      `${this.formatFeature(f["storageBytes"])} storage`,
    ];
  }

  private formatFeature(value: unknown): string {
    if (value === null || value === undefined) return "Bez limitu";
    if (typeof value === "boolean") return value ? "Tak" : "—";
    if (typeof value === "number" && value > 1024 * 1024) {
      return this.formatBytes(value);
    }
    return String(value);
  }

  private formatBytes(bytes: number): string {
    const mb = 1024 * 1024;
    if (bytes >= 1024 * mb) return `${(bytes / (1024 * mb)).toFixed(0)} GB`;
    return `${(bytes / mb).toFixed(0)} MB`;
  }
}
