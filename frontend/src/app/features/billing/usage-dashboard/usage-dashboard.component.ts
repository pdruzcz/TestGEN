import { DatePipe } from "@angular/common";
import { Component, OnInit, computed, inject, signal } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { RouterLink } from "@angular/router";

import { BillingService, UsageDashboard } from "../billing.service";
import { UsageCardComponent } from "./usage-card/usage-card.component";

/**
 * Dashboard zużycia zasobów (Story 7.9, AC1/AC2/AC4): nagłówek z okresem
 * rozliczeniowym i planem, karty zasobów z paskami postępu, prognoza
 * osiągnięcia limitu analiz z CTA „Uaktualnij plan".
 */
@Component({
  selector: "app-usage-dashboard",
  imports: [
    DatePipe,
    RouterLink,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    UsageCardComponent,
  ],
  templateUrl: "./usage-dashboard.component.html",
  styleUrl: "./usage-dashboard.component.scss",
  providers: [BillingService, DatePipe],
})
export class UsageDashboardComponent implements OnInit {
  private readonly billing = inject(BillingService);
  private readonly datePipe = inject(DatePipe);

  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly dashboard = signal<UsageDashboard | null>(null);

  /** AC2 — „{data_start} — {data_koniec}". */
  readonly periodLabel = computed(() => {
    const d = this.dashboard();
    if (!d) {
      return "";
    }
    const start = this.datePipe.transform(d.currentPeriod.start, "dd.MM.yyyy");
    const end = this.datePipe.transform(d.currentPeriod.end, "dd.MM.yyyy");
    return `${start} — ${end}`;
  });

  /** AC2 — „Plan Freemium" / „Plan Basic" / „Plan Premium". */
  readonly planLabel = computed(() => {
    const plan = this.dashboard()?.plan;
    if (!plan) {
      return "Plan —";
    }
    return `Plan ${plan.charAt(0).toUpperCase()}${plan.slice(1)}`;
  });

  /** AC2 — „Pozostało {N} dni" (1 → „dzień"). */
  readonly daysLabel = computed(() => {
    const days = this.dashboard()?.daysRemaining ?? 0;
    return `Pozostało ${days} ${days === 1 ? "dzień" : "dni"}`;
  });

  /** AC4 — prognoza przekroczenia przed końcem okresu (ostrzeżenie + CTA). */
  readonly forecastWarning = computed(
    () => this.dashboard()?.forecast?.exceedsBeforePeriodEnd === true,
  );

  /** AC4 — „Przy obecnym tempie osiągniesz limit analiz około {data}". */
  readonly forecastLabel = computed(() => {
    const forecast = this.dashboard()?.forecast;
    if (!forecast) {
      return "";
    }
    const date = this.datePipe.transform(forecast.limitDate, "dd.MM.yyyy");
    return `Przy obecnym tempie osiągniesz limit analiz około ${date}.`;
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.error.set(null);
    this.billing.getUsageDashboard().subscribe({
      next: (dashboard) => {
        this.dashboard.set(dashboard);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.errorMessage(err?.status));
        this.loading.set(false);
      },
    });
  }

  private errorMessage(status: number | undefined): string {
    if (status === 404) {
      return "Nie znaleziono subskrypcji dla tego konta — skontaktuj się z administratorem.";
    }
    return "Nie udało się pobrać danych zużycia. Spróbuj ponownie za chwilę.";
  }
}
