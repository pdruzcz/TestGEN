import { Component, inject, signal, computed, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { forkJoin, of } from "rxjs";
import { catchError } from "rxjs/operators";
import { DocumentService } from "../../projects/services/document.service";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatSelectModule } from "@angular/material/select";
import { MatChipsModule } from "@angular/material/chips";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { NavbarComponent } from "../../../shared/components/navbar.component";
import { FooterComponent } from "../../../shared/components/footer.component";
import { DocumentAnalysisService } from "../../../services/document-analysis.service";

interface GapAnalysisResult {
  requirementId: string;
  /** Widok projektowy: dokument źródłowy. */
  documentFilename?: string | null;
  requirementText: string;
  status: "implemented" | "not_implemented" | "partial" | "divergent";
  mappedEntities: string[];
  issueDescription: string | null;
  confidence: number;
}

interface CoverageSummary {
  totalRequirements: number;
  implemented: number;
  notImplemented: number;
  partial: number;
  divergent: number;
  coveragePercentage: number;
  criticalGaps: string[];
}

@Component({
  selector: "app-gap-analysis-viewer",
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatIconModule,
    MatInputModule,
    MatFormFieldModule,
    MatSelectModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    MatProgressBarModule,
    RouterLink,
    NavbarComponent,
    FooterComponent,
  ],
  template: `
    <div class="view-page">
      <app-navbar activeLink="projects" />

      <main class="view-content" id="main-content" tabindex="-1">
        <!-- Header -->
        <div class="page-header">
          <a
            mat-button
            [routerLink]="['/projects', projectId(), 'requirements']"
            class="back-link"
          >
            <mat-icon>arrow_back</mat-icon>
            Wróć do wymagań
          </a>

          @if (documentTitle()) {
            <div class="header-info">
              <h1 class="page-title">
                <mat-icon aria-hidden="true">analytics</mat-icon>
                Analiza pokrycia: {{ documentTitle() }}
              </h1>
              @if (coverageSummary()) {
                <div
                  class="coverage-badge"
                  [class.good]="coverageSummary()!.coveragePercentage >= 80"
                  [class.fair]="
                    coverageSummary()!.coveragePercentage >= 50 &&
                    coverageSummary()!.coveragePercentage < 80
                  "
                  [class.poor]="coverageSummary()!.coveragePercentage < 50"
                >
                  {{ coverageSummary()!.coveragePercentage.toFixed(0) }}%
                  pokrycia
                </div>
              }
            </div>
          }

          @if (isLoading()) {
            <div class="loading" role="status" aria-live="polite">
              <mat-spinner diameter="24" aria-label="Ładowanie"></mat-spinner>
              <span>Analizowanie pokrycia kodu…</span>
            </div>
          }
        </div>

        <!-- Coverage Summary -->
        @if (!isLoading() && coverageSummary()) {
          <div class="coverage-summary">
            <div class="summary-card">
              <mat-icon aria-hidden="true">assessment</mat-icon>
              <div class="summary-content">
                <span class="label">Całkowite pokrycie</span>
                <span class="value"
                  >{{ coverageSummary()!.coveragePercentage.toFixed(1) }}%</span
                >
              </div>
            </div>

            <div class="summary-card success">
              <mat-icon aria-hidden="true">check_circle</mat-icon>
              <div class="summary-content">
                <span class="label">Zaimplementowane</span>
                <span class="value">{{ coverageSummary()!.implemented }}</span>
              </div>
            </div>

            <div class="summary-card warning">
              <mat-icon aria-hidden="true">schedule</mat-icon>
              <div class="summary-content">
                <span class="label">Częściowe</span>
                <span class="value">{{ coverageSummary()!.partial }}</span>
              </div>
            </div>

            <div class="summary-card error">
              <mat-icon aria-hidden="true">cancel</mat-icon>
              <div class="summary-content">
                <span class="label">Brak implementacji</span>
                <span class="value">{{
                  coverageSummary()!.notImplemented
                }}</span>
              </div>
            </div>

            <div class="summary-card critical">
              <mat-icon aria-hidden="true">error</mat-icon>
              <div class="summary-content">
                <span class="label">Rozbieżności</span>
                <span class="value">{{ coverageSummary()!.divergent }}</span>
              </div>
            </div>
          </div>

          <!-- Progress Bar -->
          <div class="progress-section">
            <div class="progress-label">Postęp implementacji</div>
            <mat-progress-bar
              mode="determinate"
              [value]="coverageSummary()!.coveragePercentage"
              [color]="
                coverageSummary()!.coveragePercentage >= 80
                  ? 'primary'
                  : coverageSummary()!.coveragePercentage >= 50
                    ? 'warn'
                    : 'accent'
              "
              aria-label="Postęp implementacji"
            ></mat-progress-bar>
          </div>
        }

        <!-- Filters -->
        @if (!isLoading() && analysisResults().length > 0) {
          <div class="filters">
            <mat-form-field appearance="outline" class="filter-field">
              <mat-icon matPrefix>filter_list</mat-icon>
              <mat-label>Status</mat-label>
              <mat-select [(value)]="selectedStatus">
                <mat-option value="all">Wszystkie</mat-option>
                <mat-option value="implemented">Zaimplementowane</mat-option>
                <mat-option value="partial">Częściowe</mat-option>
                <mat-option value="not_implemented"
                  >Brak implementacji</mat-option
                >
                <mat-option value="divergent">Rozbieżności</mat-option>
              </mat-select>
            </mat-form-field>

            <mat-form-field appearance="outline" class="search-field">
              <mat-icon matPrefix>search</mat-icon>
              <input
                matInput
                placeholder="Szukaj wymagań…"
                [value]="searchQuery()"
                (input)="searchQuery.set($any($event.target).value)"
              />
            </mat-form-field>

            @if (coverageSummary()?.criticalGaps?.length) {
              <div class="critical-alert">
                <mat-icon aria-hidden="true">warning</mat-icon>
                <span
                  >{{ coverageSummary()!.criticalGaps?.length ?? 0 }} luk
                  krytycznych</span
                >
              </div>
            }
          </div>
        }

        <!-- Analysis Results -->
        @if (!isLoading()) {
          @if (filteredResults().length > 0) {
            <div class="results-list">
              @for (result of filteredResults(); track result.requirementId) {
                <div
                  class="result-card"
                  [class.status-implemented]="result.status === 'implemented'"
                  [class.status-partial]="result.status === 'partial'"
                  [class.status-not-implemented]="
                    result.status === 'not_implemented'
                  "
                  [class.status-divergent]="result.status === 'divergent'"
                >
                  <div class="card-header">
                    <div class="header-left">
                      <span class="req-id">{{ result.requirementId }}</span>
                      @if (isProjectView() && result.documentFilename) {
                        <span class="doc-badge" title="Dokument źródłowy">{{
                          result.documentFilename
                        }}</span>
                      }
                      <mat-chip [color]="getStatusColor(result.status)">
                        {{ getStatusLabel(result.status) }}
                      </mat-chip>
                      <div class="confidence">
                        <mat-icon aria-hidden="true"
                          >confidence_interval</mat-icon
                        >
                        {{ result.confidence.toFixed(0) }}%
                      </div>
                    </div>
                  </div>

                  <div class="card-content">
                    <p class="req-text">{{ result.requirementText }}</p>

                    @if (result.mappedEntities?.length) {
                      <div class="mapped-entities">
                        <mat-icon aria-hidden="true">code</mat-icon>
                        <strong>Zmapowane encje:</strong>
                        <div class="entity-list">
                          @for (entity of result.mappedEntities; track entity) {
                            <code class="entity">{{ entity }}</code>
                          }
                        </div>
                      </div>
                    }

                    @if (result.issueDescription) {
                      <div class="issue-description">
                        <mat-icon aria-hidden="true">info</mat-icon>
                        <span>{{ result.issueDescription }}</span>
                      </div>
                    }
                  </div>

                  <div class="card-actions">
                    @if (
                      result.status === "not_implemented" ||
                      result.status === "divergent"
                    ) {
                      <button mat-button color="primary">
                        <mat-icon aria-hidden="true">add_task</mat-icon>
                        Utwórz zadanie
                      </button>
                    }
                    @if (result.status === "partial") {
                      <button mat-button>
                        <mat-icon aria-hidden="true">build</mat-icon>
                        Dokończ implementację
                      </button>
                    }
                    <button mat-button>
                      <mat-icon aria-hidden="true">visibility</mat-icon>
                      Pokaż w kodzie
                    </button>
                  </div>
                </div>
              }
            </div>
          } @else if (analysisResults().length === 0) {
            <div class="empty-state">
              <mat-icon aria-hidden="true">analytics</mat-icon>
              <p>Brak wyników analizy pokrycia.</p>
              <p class="hint">
                Prześlij kod do analizy, aby zobaczyć pokrycie wymagań.
              </p>
              <button mat-button color="primary">
                <mat-icon aria-hidden="true">upload</mat-icon>
                Prześlij kod
              </button>
            </div>
          } @else {
            <div class="empty-state">
              <mat-icon aria-hidden="true">search_off</mat-icon>
              <p>Brak wyników spełniających kryteria filtru.</p>
              <button mat-button (click)="clearFilters()">
                Wyczyść filtry
              </button>
            </div>
          }
        }

        <!-- Critical Gaps Alert -->
        @if (
          !isLoading() &&
          coverageSummary() &&
          (coverageSummary()!.criticalGaps?.length ?? 0) > 0
        ) {
          <div class="critical-gaps-alert">
            <mat-icon aria-hidden="true">error_outline</mat-icon>
            <div class="alert-content">
              <h3>Wykryto luki krytyczne</h3>
              <p>Następujące wymagania nie są zaimplementowane:</p>
              <div class="gap-list">
                @for (gapId of coverageSummary()!.criticalGaps; track gapId) {
                  <mat-chip class="gap-chip">
                    {{ gapId }}
                  </mat-chip>
                }
              </div>
            </div>
            <button mat-button color="warn">
              <mat-icon aria-hidden="true">priority_high</mat-icon>
              Priorytetuj zadania
            </button>
          </div>
        }

        <!-- Action Bar -->
        @if (filteredResults().length > 0) {
          <div class="action-bar">
            <button mat-button color="primary">
              <mat-icon aria-hidden="true">add_task</mat-icon>
              Utwórz zadania dla braków
            </button>
            <button mat-button>
              <mat-icon aria-hidden="true">download</mat-icon>
              Eksportuj raport
            </button>
            <button mat-button>
              <mat-icon aria-hidden="true">refresh</mat-icon>
              Odśwież analizę
            </button>
          </div>
        }
      </main>

      <app-footer />
    </div>
  `,
  styles: [
    `
      .doc-badge {
        font-size: 11px;
        color: #4b5563;
        background: #f3f4f6;
        border: 1px solid #d1d5db;
        border-radius: 6px;
        padding: 1px 6px;
        margin-left: 6px;
      }
    `,
    `
      .view-page {
        min-height: 100vh;
        background: #f7f8fa;
        display: flex;
        flex-direction: column;
      }

      .view-content {
        flex: 1;
        padding: 32px 48px;
        max-width: 1200px;
        width: 100%;
        margin: 0 auto;
      }

      .page-header {
        margin-bottom: 24px;
      }

      .back-link {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        margin-bottom: 16px;
      }

      .header-info {
        display: flex;
        align-items: center;
        gap: 16px;
        flex-wrap: wrap;
      }

      .page-title {
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 24px;
        font-weight: 700;
        color: #1a1a1a;
        margin: 0;
      }

      .page-title mat-icon {
        font-size: 32px;
        height: 32px;
        width: 32px;
        color: #3b82f6;
      }

      .coverage-badge {
        padding: 8px 16px;
        border-radius: 20px;
        font-size: 16px;
        font-weight: 600;
      }

      .coverage-badge.good {
        background: #d1fae5;
        color: #065f46;
      }

      .coverage-badge.fair {
        background: #fef3c7;
        color: #92400e;
      }

      .coverage-badge.poor {
        background: #fee2e2;
        color: #991b1b;
      }

      .loading {
        display: flex;
        align-items: center;
        gap: 12px;
        color: #6b7280;
      }

      .coverage-summary {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 16px;
        margin-bottom: 24px;
      }

      .summary-card {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 16px;
        background: #ffffff;
        border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
      }

      .summary-card.success {
        border-left: 4px solid #10b981;
      }

      .summary-card.warning {
        border-left: 4px solid #f59e0b;
      }

      .summary-card.error {
        border-left: 4px solid #ef4444;
      }

      .summary-card.critical {
        border-left: 4px solid #7c3aed;
      }

      .summary-card mat-icon {
        font-size: 28px;
        height: 28px;
        width: 28px;
        color: #6b7280;
      }

      .summary-content {
        display: flex;
        flex-direction: column;
      }

      .summary-content .label {
        font-size: 12px;
        color: #6b7280;
      }

      .summary-content .value {
        font-size: 20px;
        font-weight: 700;
        color: #1a1a1a;
      }

      .progress-section {
        margin-bottom: 24px;
      }

      .progress-label {
        font-size: 14px;
        color: #6b7280;
        margin-bottom: 8px;
      }

      .filters {
        display: flex;
        gap: 16px;
        align-items: center;
        margin-bottom: 24px;
        flex-wrap: wrap;
      }

      .filter-field {
        width: 220px;
      }

      .search-field {
        flex: 1;
        min-width: 250px;
      }

      .critical-alert {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 16px;
        background: #fef3c7;
        color: #92400e;
        border-radius: 8px;
        font-weight: 500;
      }

      .critical-alert mat-icon {
        font-size: 20px;
        width: 20px;
        height: 20px;
      }

      .results-list {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }

      .result-card {
        background: #ffffff;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        border-left: 4px solid #d1d5db;
      }

      .result-card.status-implemented {
        border-left-color: #10b981;
      }

      .result-card.status-partial {
        border-left-color: #f59e0b;
      }

      .result-card.status-not-implemented {
        border-left-color: #ef4444;
      }

      .result-card.status-divergent {
        border-left-color: #7c3aed;
      }

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 16px;
      }

      .header-left {
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .req-id {
        font-weight: 600;
        color: #1e40af;
        font-size: 14px;
      }

      .confidence {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 13px;
        color: #6b7280;
      }

      .confidence mat-icon {
        font-size: 16px;
        width: 16px;
        height: 16px;
      }

      .card-content {
        display: flex;
        flex-direction: column;
        gap: 12px;
        margin-bottom: 16px;
      }

      .req-text {
        margin: 0;
        color: #374151;
        line-height: 1.6;
      }

      .mapped-entities {
        display: flex;
        align-items: flex-start;
        gap: 8px;
        padding: 12px;
        background: #f0fdf4;
        border-radius: 8px;
      }

      .mapped-entities mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
        color: #16a34a;
        flex-shrink: 0;
        margin-top: 2px;
      }

      .entity-list {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }

      .entity {
        padding: 4px 10px;
        background: #ffffff;
        border: 1px solid #86efac;
        border-radius: 4px;
        font-family: monospace;
        font-size: 12px;
        color: #16a34a;
      }

      .issue-description {
        display: flex;
        align-items: flex-start;
        gap: 8px;
        padding: 12px;
        background: #fef3c7;
        border-radius: 8px;
      }

      .issue-description mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
        color: #92400e;
        flex-shrink: 0;
        margin-top: 2px;
      }

      .card-actions {
        display: flex;
        gap: 8px;
        padding-top: 12px;
        border-top: 1px solid #e5e7eb;
      }

      .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 16px;
        padding: 64px 32px;
        text-align: center;
        color: #6b7280;
      }

      .empty-state mat-icon {
        font-size: 64px;
        height: 64px;
        width: 64px;
        color: #d1d5db;
      }

      .hint {
        color: #9ca3af;
        font-size: 14px;
      }

      .critical-gaps-alert {
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 20px;
        background: #fef3c7;
        border: 2px solid #f59e0b;
        border-radius: 12px;
        margin-bottom: 24px;
      }

      .critical-gaps-alert mat-icon {
        font-size: 32px;
        height: 32px;
        width: 32px;
        color: #92400e;
      }

      .alert-content h3 {
        margin: 0 0 8px 0;
        color: #92400e;
      }

      .alert-content p {
        margin: 0 0 12px 0;
        color: #78350f;
      }

      .gap-list {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }

      .gap-chip {
        background: #fef2f2;
        color: #991b1b;
      }

      .action-bar {
        display: flex;
        gap: 12px;
        margin-top: 24px;
        padding-top: 24px;
        border-top: 1px solid #e5e7eb;
      }

      @media (max-width: 768px) {
        .view-content {
          padding: 16px;
        }

        .coverage-summary {
          grid-template-columns: repeat(2, 1fr);
        }

        .filters {
          flex-direction: column;
          align-items: stretch;
        }

        .filter-field,
        .search-field {
          width: 100%;
        }
      }
    `,
  ],
})
export class GapAnalysisViewerComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly documentService = inject(DocumentAnalysisService);
  private readonly docsService = inject(DocumentService);

  readonly analysisResults = signal<GapAnalysisResult[]>([]);
  readonly coverageSummary = signal<CoverageSummary | null>(null);
  readonly isLoading = signal(false);
  readonly documentTitle = signal("");
  readonly searchQuery = signal("");
  readonly selectedStatus = signal("all");
  readonly documentId = signal("");

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  readonly documentIdFromQuery = computed(
    () => this.route.snapshot.queryParamMap.get("documentId") || "",
  );

  readonly filteredResults = computed(() => {
    let results = this.analysisResults();

    if (this.selectedStatus() !== "all") {
      results = results.filter((r) => r.status === this.selectedStatus());
    }

    const query = this.searchQuery().toLowerCase().trim();
    if (query) {
      results = results.filter(
        (r) =>
          r.requirementText.toLowerCase().includes(query) ||
          r.requirementId.toLowerCase().includes(query),
      );
    }

    return results;
  });

  ngOnInit(): void {
    const docId =
      this.documentIdFromQuery() ||
      this.route.snapshot.queryParams["documentId"];

    if (docId) {
      this.documentId.set(docId);
      this.loadGapAnalysis(docId);
    } else {
      // Widok nawigacji projektu: raport pokrycia scalony ze wszystkich
      // dokumentów projektu (formuła BE: implemented/total).
      this.loadProjectCoverage();
    }
  }

  /** true, gdy raport obejmuje wszystkie dokumenty projektu. */
  readonly isProjectView = computed(() => this.documentId() === "");

  private loadProjectCoverage(): void {
    this.isLoading.set(true);
    this.docsService.listDocuments(this.projectId(), 1, 100).subscribe({
      next: ({ documents }) => {
        if (!documents.length) {
          this.documentTitle.set("Brak dokumentów w projekcie");
          this.isLoading.set(false);
          return;
        }
        forkJoin(
          documents.map((d) =>
            this.documentService
              .getAnalysisResults(d.id)
              .pipe(catchError(() => of(null as any))),
          ),
        ).subscribe((results) => {
          let total = 0;
          let implemented = 0;
          let notImplemented = 0;
          let partial = 0;
          let divergent = 0;
          const criticalGaps: string[] = [];
          const items: any[] = [];
          let withReport = 0;
          results.forEach((res, i) => {
            if (!res) return;
            withReport++;
            const gapAnalysis = (res as any).gapAnalysis ?? {};
            const s = gapAnalysis.summary;
            if (s) {
              total += s.totalRequirements ?? 0;
              implemented += s.implemented ?? 0;
              notImplemented += s.notImplemented ?? 0;
              partial += s.partial ?? 0;
              divergent += s.divergent ?? 0;
              criticalGaps.push(...(s.criticalGaps ?? []));
            }
            (gapAnalysis.items ?? []).forEach((it: any) =>
              items.push({ ...it, documentFilename: documents[i].filename }),
            );
          });
          this.documentTitle.set(
            `Wszystkie dokumenty (${withReport}/${documents.length})`,
          );
          this.coverageSummary.set({
            totalRequirements: total,
            implemented,
            notImplemented: notImplemented,
            partial,
            divergent,
            coveragePercentage: total > 0 ? (implemented / total) * 100 : 0,
            criticalGaps: criticalGaps,
          });
          this.analysisResults.set(items);
          this.isLoading.set(false);
        });
      },
      error: () => this.isLoading.set(false),
    });
  }

  private loadGapAnalysis(documentId: string): void {
    this.isLoading.set(true);

    this.documentService.getAnalysisResults(documentId).subscribe({
      next: (response) => {
        this.documentTitle.set(response.filename);

        // Story 2.8: gap analysis is persisted as { summary, items }.
        // ``summary`` holds the coverage report; ``items`` holds the full
        // per-requirement list (not only criticalGaps as before).
        const gapAnalysis = response.gapAnalysis ?? {};
        const summary = gapAnalysis.summary;
        this.coverageSummary.set({
          totalRequirements: summary?.totalRequirements ?? 0,
          implemented: summary?.implemented ?? 0,
          notImplemented: summary?.notImplemented ?? 0,
          partial: summary?.partial ?? 0,
          divergent: summary?.divergent ?? 0,
          coveragePercentage: summary?.coveragePercentage ?? 0,
          criticalGaps: summary?.criticalGaps ?? [],
        });

        this.analysisResults.set(
          (gapAnalysis.items ?? []) as GapAnalysisResult[],
        );
        this.isLoading.set(false);
      },
      error: (err) => {
        console.error("Failed to load gap analysis:", err);
        this.isLoading.set(false);
      },
    });
  }

  clearFilters(): void {
    this.selectedStatus.set("all");
    this.searchQuery.set("");
  }

  getStatusLabel(status: string): string {
    const labels: Record<string, string> = {
      implemented: "Zaimplementowane",
      not_implemented: "Brak implementacji",
      partial: "Częściowe",
      divergent: "Rozbieżności",
    };
    return labels[status] || status;
  }

  getStatusColor(status: string): string {
    const colors: Record<string, string> = {
      implemented: "primary",
      partial: "accent",
      not_implemented: "warn",
      divergent: "",
    };
    return colors[status] || "";
  }
}
