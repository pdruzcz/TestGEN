import {
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  signal,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatCardModule } from "@angular/material/card";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { NavbarComponent } from "../../../shared/components/navbar.component";
import { FooterComponent } from "../../../shared/components/footer.component";
import {
  GuiAnalysisOption,
  HealingAction,
  HealingItem,
  HealingReport,
  HealingService,
} from "./services/healing.service";

/**
 * Story 1.51: self-healing of broken UI-test locators between two GUI versions.
 * Mirrors the scan-launcher flow (launch → poll → review). `healing_method`
 * stays in the backend/API only — it is never surfaced as a GUI toggle (the
 * engine_mode decision is config-only, not user-controllable).
 */
@Component({
  selector: "app-healing",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    MatButtonModule,
    MatIconModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatProgressSpinnerModule,
    NavbarComponent,
    FooterComponent,
  ],
  templateUrl: "./healing.component.html",
  styleUrls: ["./healing.component.scss"],
})
export class HealingComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly service = inject(HealingService);

  readonly projectId = signal("");
  readonly versionA = signal("");
  readonly versionB = signal("");
  readonly analyses = signal<GuiAnalysisOption[]>([]);
  readonly isLaunching = signal(false);
  readonly report = signal<HealingReport | null>(null);
  readonly errorMessage = signal<string | null>(null);

  private reportId: string | null = null;
  private pollHandle: ReturnType<typeof setInterval> | null = null;
  private pollAttempts = 0;
  private static readonly MAX_POLL_ATTEMPTS = 15;

  readonly canLaunch = computed(
    () =>
      !!this.versionA().trim() &&
      !!this.versionB().trim() &&
      this.versionA().trim() !== this.versionB().trim() &&
      !this.isLaunching(),
  );

  ngOnInit(): void {
    this.projectId.set(this.route.snapshot.paramMap.get("projectId") ?? "");
    this.loadAnalyses();
  }

  /** Format a GUI analysis as a launcher option label (source · file · date). */
  analysisLabel(a: GuiAnalysisOption): string {
    const source = a.sourceType === "dom" ? "DOM" : "zrzut";
    const label = a.sourceLabel ?? "analiza GUI";
    const ver = a.versionLabel ? ` · ${a.versionLabel}` : "";
    const date = a.createdAt
      ? " · " + new Date(a.createdAt).toLocaleDateString("pl-PL")
      : "";
    return `${source} · ${label}${ver}${date}`;
  }

  private loadAnalyses(): void {
    if (!this.projectId()) return;
    this.service
      .getGuiAnalyses(this.projectId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => this.analyses.set(res.analyses ?? []),
        error: () => this.analyses.set([]),
      });
  }

  launch(): void {
    if (!this.projectId() || !this.canLaunch()) return;
    this.isLaunching.set(true);
    this.errorMessage.set(null);
    this.report.set(null);
    this.service
      .heal(this.projectId(), this.versionA().trim(), this.versionB().trim())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.isLaunching.set(false);
          this.reportId = res.reportId;
          this.startPolling();
        },
        error: () => {
          this.isLaunching.set(false);
          this.errorMessage.set("Uruchomienie healingu nie powiodło się.");
        },
      });
  }

  refresh(): void {
    if (this.projectId() && this.reportId) this.loadReport();
  }

  decide(item: HealingItem, action: HealingAction): void {
    if (!this.projectId() || !this.reportId) return;
    this.service
      .decide(this.projectId(), this.reportId, item.id, action)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (decision) => {
          const current = this.report();
          if (!current) return;
          this.report.set({
            ...current,
            items: current.items.map((it) =>
              it.id === decision.itemId
                ? { ...it, status: decision.status }
                : it,
            ),
          });
        },
        error: () =>
          this.errorMessage.set(
            action === "accept"
              ? "Akceptacja naprawy nie powiodła się."
              : "Odrzucenie nie powiodło się.",
          ),
      });
  }

  confidenceClass(c: number): string {
    if (c >= 0.8) return "conf-high";
    if (c >= 0.4) return "conf-mid";
    return "conf-low";
  }

  strategyLabel(strategy: string | null): string {
    const map: Record<string, string> = {
      "data-testid": "data-testid",
      "role+name": "rola + nazwa",
      "aria-label": "aria-label",
      id: "id",
      css: "CSS",
      xpath: "XPath",
    };
    return strategy ? (map[strategy] ?? strategy) : "—";
  }

  statusLabel(status: string): string {
    const map: Record<string, string> = {
      pending: "Oczekuje",
      healed: "Naprawiony",
      needs_review: "Do przeglądu",
      failed: "Nieudany",
      rejected: "Odrzucony",
    };
    return map[status] ?? status;
  }

  private startPolling(): void {
    this.stopPolling();
    this.pollAttempts = 0;
    this.loadReport();
    this.pollHandle = setInterval(() => {
      this.pollAttempts += 1;
      if (this.pollAttempts > HealingComponent.MAX_POLL_ATTEMPTS) {
        this.stopPolling();
        return;
      }
      this.loadReport();
    }, 2000);
  }

  private stopPolling(): void {
    if (this.pollHandle) {
      clearInterval(this.pollHandle);
      this.pollHandle = null;
    }
  }

  private loadReport(): void {
    if (!this.projectId() || !this.reportId) return;
    this.service
      .getReport(this.projectId(), this.reportId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (rep) => {
          this.report.set(rep);
          if (rep.status !== "pending") this.stopPolling();
        },
        error: () =>
          this.errorMessage.set("Nie udało się pobrać raportu healingu."),
      });
  }

  constructor() {
    this.destroyRef.onDestroy(() => this.stopPolling());
  }
}
