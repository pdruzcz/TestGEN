import { Component, DestroyRef, OnInit, inject, signal } from "@angular/core";
import { CommonModule } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatTableModule } from "@angular/material/table";
import { MatPaginatorModule, PageEvent } from "@angular/material/paginator";
import { MatSelectModule } from "@angular/material/select";
import { MatTooltipModule } from "@angular/material/tooltip";
import { NavbarComponent } from "../../shared/components/navbar.component";
import { FooterComponent } from "../../shared/components/footer.component";
import {
  GapAnalysisService,
  GapFinding,
  GapAnalysisSummary,
  SkeletonResponse,
} from "./services/gap-analysis.service";

@Component({
  selector: "app-gap-analysis-epic5",
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatTableModule,
    MatPaginatorModule,
    MatSelectModule,
    MatTooltipModule,
    NavbarComponent,
    FooterComponent,
  ],
  template: `
    <div class="ga-page">
      <app-navbar activeLink="projects" />
      <main class="ga-content" id="main-content" tabindex="-1">
        <a mat-button routerLink="/projects" class="back-link">
          <mat-icon>arrow_back</mat-icon>
          Wróć do projektów
        </a>

        <div class="header-row">
          <h1 class="page-title">Luki funkcjonalne</h1>
          <button
            mat-raised-button
            color="primary"
            (click)="triggerAnalysis()"
            [disabled]="isTriggering()"
          >
            <mat-icon>{{
              isTriggering() ? "hourglass_empty" : "play_arrow"
            }}</mat-icon>
            Uruchom analizę
          </button>
        </div>

        @if (triggerStatus()) {
          <div
            class="trigger-info"
            [class.error]="triggerStatus()?.includes('Błąd')"
          >
            {{ triggerStatus() }}
          </div>
        }

        @if (isLoading()) {
          <mat-spinner diameter="40" aria-label="Ładowanie" />
        } @else {
          @if (summary()) {
            <div class="summary-grid">
              <div class="summary-card">
                <span class="summary-value"
                  >{{ summary()!.coveragePercentage }}%</span
                >
                <span class="summary-label">Pokrycie</span>
              </div>
              <div class="summary-card missing">
                <span class="summary-value">{{ summary()!.missingCount }}</span>
                <span class="summary-label">Brakujące</span>
              </div>
              <div class="summary-card different">
                <span class="summary-value">{{
                  summary()!.differentCount
                }}</span>
                <span class="summary-label">Różne</span>
              </div>
              <div class="summary-card extra">
                <span class="summary-value">{{ summary()!.extraCount }}</span>
                <span class="summary-label">Nadmiarowe</span>
              </div>
              <div class="summary-card inconsistent">
                <span class="summary-value">{{
                  summary()!.inconsistentCount
                }}</span>
                <span class="summary-label">Niespójne</span>
              </div>
              <div class="summary-card">
                <span class="summary-value">{{
                  summary()!.avgMatchScore
                }}</span>
                <span class="summary-label">Średni wynik</span>
              </div>
            </div>
          }

          <div class="filters-row">
            <mat-form-field appearance="outline" class="filter-select">
              <mat-label>Typ luki</mat-label>
              <mat-select
                [value]="filterGapType()"
                (selectionChange)="onFilterChange('gapType', $event.value)"
              >
                <mat-option value="">Wszystkie</mat-option>
                <mat-option value="missing">Brakujące</mat-option>
                <mat-option value="different">Różne</mat-option>
                <mat-option value="extra">Nadmiarowe</mat-option>
                <mat-option value="inconsistent">Niespójne</mat-option>
              </mat-select>
            </mat-form-field>

            <mat-form-field appearance="outline" class="filter-select">
              <mat-label>Severity</mat-label>
              <mat-select
                [value]="filterSeverity()"
                (selectionChange)="onFilterChange('severity', $event.value)"
              >
                <mat-option value="">Wszystkie</mat-option>
                <mat-option value="critical">Krytyczny</mat-option>
                <mat-option value="warning">Ostrzeżenie</mat-option>
                <mat-option value="info">Info</mat-option>
              </mat-select>
            </mat-form-field>

            <button
              mat-stroked-button
              (click)="loadFindings()"
              class="refresh-btn"
            >
              <mat-icon>refresh</mat-icon>
              Odśwież
            </button>
          </div>

          @if (findings().length > 0) {
            <table mat-table [dataSource]="findings()" class="findings-table">
              <caption class="visually-hidden">Lista wykrytych luk w analizie</caption>
              <ng-container matColumnDef="gapType">
                <th mat-header-cell *matHeaderCellDef scope="col">Typ</th>
                <td mat-cell *matCellDef="let f">
                  <span class="gap-chip" [class]="'chip-' + f.gapType">
                    {{ gapTypeLabel(f.gapType) }}
                  </span>
                </td>
              </ng-container>

              <ng-container matColumnDef="requirement">
                <th mat-header-cell *matHeaderCellDef scope="col">Wymaganie</th>
                <td mat-cell *matCellDef="let f" class="req-cell">
                  <div class="req-id">{{ f.requirementId || "—" }}</div>
                  <div class="req-text">
                    {{ f.requirementText || f.description }}
                  </div>
                </td>
              </ng-container>

              <ng-container matColumnDef="codeEntity">
                <th mat-header-cell *matHeaderCellDef scope="col">Byt kodu</th>
                <td mat-cell *matCellDef="let f">
                  {{ f.codeEntityId || "—" }}
                  @if (f.codeReference) {
                    <div class="code-ref">{{ f.codeReference }}</div>
                  }
                </td>
              </ng-container>

              <ng-container matColumnDef="score">
                <th mat-header-cell *matHeaderCellDef scope="col">Wynik (%)</th>
                <td mat-cell *matCellDef="let f">
                  <div class="score-bar">
                    <div
                      class="score-fill"
                      [style.width.%]="f.matchScore"
                    ></div>
                    <span class="score-text">{{
                      f.matchScore.toFixed(1)
                    }}</span>
                  </div>
                </td>
              </ng-container>

              <ng-container matColumnDef="method">
                <th mat-header-cell *matHeaderCellDef scope="col">Metoda</th>
                <td mat-cell *matCellDef="let f">{{ f.matchMethod || "—" }}</td>
              </ng-container>

              <ng-container matColumnDef="severity">
                <th mat-header-cell *matHeaderCellDef scope="col">Severity</th>
                <td mat-cell *matCellDef="let f">
                  <span class="severity-badge" [class]="'sev-' + f.severity">
                    {{ severityLabel(f.severity) }}
                  </span>
                </td>
              </ng-container>

              <ng-container matColumnDef="skeleton">
                <th mat-header-cell *matHeaderCellDef scope="col">Skeleton</th>
                <td mat-cell *matCellDef="let f">
                  @if (f.gapType === "missing") {
                    @if (skeletonPreview()[f.id]) {
                      <span class="skel-badge skel-done">Gotowy</span>
                    } @else if (f.skeletonCode) {
                      <span class="skel-badge skel-done">Zapisany</span>
                    } @else if (skeletonGenerating() === f.id) {
                      <mat-spinner diameter="16" aria-label="Ładowanie" />
                    } @else {
                      <button
                        mat-stroked-button
                        class="skel-btn"
                        (click)="generateSkeleton(f, $event)"
                      >
                        <mat-icon>code</mat-icon>
                        Generuj
                      </button>
                    }
                  } @else {
                    <span class="skel-na">—</span>
                  }
                </td>
              </ng-container>

              <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
              <tr
                mat-row
                *matRowDef="let row; columns: displayedColumns"
                class="findings-row"
                [class.expanded]="expandedElement() === row"
                (click)="toggleExpand(row)"
              ></tr>
              @if (expandedElement()) {
                <tr class="detail-row">
                  <td colspan="7">
                    <div class="detail-content">
                      @if (expandedElement()!.context) {
                        <div class="detail-grid">
                          @if (
                            expandedElement()!.context?.["requirement_excerpt"]
                          ) {
                            <div class="detail-block">
                              <span class="detail-label"
                                >Fragment wymagania:</span
                              >
                              <p class="detail-text">
                                {{
                                  expandedElement()!.context?.[
                                    "requirement_excerpt"
                                  ]
                                }}
                              </p>
                            </div>
                          }
                          @if (expandedElement()!.context?.["code_excerpt"]) {
                            <div class="detail-block">
                              <span class="detail-label">Fragment kodu:</span>
                              <p class="detail-text">
                                {{
                                  expandedElement()!.context?.["code_excerpt"]
                                }}
                              </p>
                            </div>
                          }
                          @if (expandedElement()!.context?.["best_candidate"]) {
                            <div class="detail-block">
                              <span class="detail-label"
                                >Najlepszy kandydat:</span
                              >
                              <span class="detail-text"
                                >{{
                                  expandedElement()!.context?.["best_candidate"]
                                }}
                                ({{
                                  expandedElement()!.context?.["best_score"]
                                }}%)</span
                              >
                            </div>
                          }
                          @if (expandedElement()!.context?.["file_path"]) {
                            <div class="detail-block">
                              <span class="detail-label">Lokalizacja:</span>
                              <span class="detail-text"
                                >{{
                                  expandedElement()!.context?.["file_path"]
                                }}:{{
                                  expandedElement()!.context?.["line_number"]
                                }}</span
                              >
                            </div>
                          }
                        </div>
                      }
                      @if (skeletonPreview()[expandedElement()!.id]) {
                        <div class="skeleton-section">
                          <div class="skeleton-header">
                            <span class="detail-label">Skeleton — {{ skeletonPreview()[expandedElement()!.id].language }}</span>
                            <button
                              mat-stroked-button
                              class="copy-btn"
                              (click)="copySkeleton(skeletonPreview()[expandedElement()!.id].skeletonCode)"
                            >
                              <mat-icon>content_copy</mat-icon>
                              Kopiuj
                            </button>
                          </div>
                          <pre class="skeleton-code">{{ skeletonPreview()[expandedElement()!.id].skeletonCode }}</pre>
                        </div>
                      }
                    </div>
                  </td>
                </tr>
              }
            </table>

            <mat-paginator
              [length]="total()"
              [pageSize]="pageSize()"
              [pageIndex]="pageIndex()"
              (page)="onPageChange($event)"
            />
          } @else {
            <div class="empty-state">
              <mat-icon>search_off</mat-icon>
              <p>Brak luk funkcjonalnych. Uruchom analizę, aby wykryć luki.</p>
            </div>
          }
        }
      </main>
      <app-footer />
    </div>
  `,
  styles: [
    `
      .ga-page {
        min-height: 100vh;
        background: #f7f8fa;
        display: flex;
        flex-direction: column;
      }
      .ga-content {
        flex: 1;
        padding: 32px 48px;
        max-width: 1400px;
        width: 100%;
        margin: 0 auto;
        display: flex;
        flex-direction: column;
        gap: 20px;
      }
      .back-link {
        align-self: flex-start;
      }
      .header-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
      }
      .page-title {
        font-size: 28px;
        font-weight: 700;
        color: #1a1a1a;
        margin: 0;
      }
      .trigger-info {
        padding: 12px 16px;
        border-radius: 8px;
        background: #e8f5e9;
        color: #1b5e20;
        font-size: 14px;
      }
      .trigger-info.error {
        background: #ffeef0;
        color: #b71c1c;
      }
      .summary-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
        gap: 12px;
      }
      .summary-card {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 16px;
        border-radius: 12px;
        background: white;
        border: 1px solid #e5e7eb;
      }
      .summary-card.missing {
        border-left: 4px solid #ef4444;
      }
      .summary-card.different {
        border-left: 4px solid #f59e0b;
      }
      .summary-card.extra {
        border-left: 4px solid #eab308;
      }
      .summary-card.inconsistent {
        border-left: 4px solid #a855f7;
      }
      .summary-value {
        font-size: 32px;
        font-weight: 700;
        color: #1a1a1a;
      }
      .summary-label {
        font-size: 13px;
        color: #6b7280;
        margin-top: 4px;
      }
      .filters-row {
        display: flex;
        gap: 12px;
        align-items: center;
        flex-wrap: wrap;
      }
      .filter-select {
        min-width: 180px;
      }
      .refresh-btn {
        margin-bottom: 12px;
      }
      .findings-table {
        width: 100%;
        background: white;
        border-radius: 8px;
      }
      .req-cell {
        max-width: 350px;
      }
      .req-id {
        font-weight: 600;
        font-size: 13px;
      }
      .req-text {
        font-size: 12px;
        color: #6b7280;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .code-ref {
        font-size: 11px;
        color: #6b7280;
        font-family: monospace;
      }
      .gap-chip {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 500;
      }
      .chip-missing {
        background: #fef2f2;
        color: #991b1b;
      }
      .chip-different {
        background: #fffbeb;
        color: #92400e;
      }
      .chip-extra {
        background: #fefce8;
        color: #854d0e;
      }
      .chip-inconsistent {
        background: #faf5ff;
        color: #6b21a8;
      }
      .score-bar {
        position: relative;
        width: 80px;
        height: 20px;
        background: #e5e7eb;
        border-radius: 4px;
        overflow: hidden;
      }
      .score-fill {
        height: 100%;
        background: #3b82f6;
        transition: width 0.3s;
      }
      .score-text {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 11px;
        font-weight: 600;
        color: #1a1a1a;
      }
      .severity-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 500;
      }
      .sev-critical {
        background: #fef2f2;
        color: #991b1b;
      }
      .sev-warning {
        background: #fffbeb;
        color: #92400e;
      }
      .sev-info {
        background: #f3f4f6;
        color: #4b5563;
      }
      .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 48px;
        color: #6b7280;
        gap: 12px;
      }
      .empty-state mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
      }
      .findings-row {
        cursor: pointer;
        transition: background 0.15s;
      }
      .findings-row:hover {
        background: #f3f4f6;
      }
      .findings-row.expanded {
        background: #f0f4ff;
      }
      .detail-row td {
        padding: 0 !important;
        border: none !important;
      }
      .detail-content {
        padding: 16px 24px;
        background: #f9fafb;
      }
      .detail-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px 24px;
      }
      .detail-block {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .detail-label {
        font-size: 11px;
        font-weight: 600;
        color: #6b7280;
        text-transform: uppercase;
      }
      .detail-text {
        font-size: 13px;
        color: #374151;
        margin: 0;
        font-family: monospace;
      }
      .skel-btn {
        font-size: 11px;
        padding: 0 8px;
      }
      .skel-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 8px;
        font-size: 11px;
        font-weight: 600;
      }
      .skel-done {
        background: #e8f5e9;
        color: #1b5e20;
      }
      .skel-na {
        color: #d1d5db;
      }
      .skeleton-section {
        grid-column: 1 / -1;
        margin-top: 8px;
      }
      .skeleton-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 8px;
      }
      .copy-btn {
        font-size: 11px;
      }
      .skeleton-code {
        background: #1e293b;
        color: #e2e8f0;
        padding: 12px 16px;
        border-radius: 8px;
        font-size: 13px;
        font-family: "Fira Code", "Courier New", monospace;
        overflow-x: auto;
        margin: 0;
      }
    `,
  ],
})
export class GapAnalysisComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly gapService = inject(GapAnalysisService);

  readonly projectId = this.route.snapshot.paramMap.get("projectId") ?? "";

  readonly isLoading = signal(true);
  readonly isTriggering = signal(false);
  readonly triggerStatus = signal<string | null>(null);
  readonly findings = signal<GapFinding[]>([]);
  readonly summary = signal<GapAnalysisSummary | null>(null);
  readonly total = signal(0);
  readonly pageIndex = signal(0);
  readonly pageSize = signal(20);
  readonly filterGapType = signal("");
  readonly filterSeverity = signal("");
  readonly expandedElement = signal<GapFinding | null>(null);
  readonly skeletonGenerating = signal<string | null>(null);
  readonly skeletonPreview = signal<Record<string, SkeletonResponse>>({});

  readonly displayedColumns = [
    "gapType",
    "requirement",
    "codeEntity",
    "score",
    "method",
    "severity",
    "skeleton",
  ];

  ngOnInit(): void {
    this.loadFindings();
  }

  loadFindings(): void {
    this.isLoading.set(true);
    this.gapService
      .getFindings(this.projectId, {
        gapType: this.filterGapType() || undefined,
        severity: this.filterSeverity() || undefined,
        page: this.pageIndex() + 1,
        size: this.pageSize(),
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (resp) => {
          this.findings.set(resp.findings);
          this.total.set(resp.total);
          this.summary.set(resp.summary);
          this.isLoading.set(false);
        },
        error: () => this.isLoading.set(false),
      });
  }

  triggerAnalysis(): void {
    this.isTriggering.set(true);
    this.triggerStatus.set(null);
    this.gapService
      .startAnalysis(this.projectId, { engineMode: "native" })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (resp) => {
          this.isTriggering.set(false);
          this.triggerStatus.set(
            `Analiza uruchomiona (task: ${resp.taskId}). Odśwież za chwilę, aby zobaczyć wyniki.`,
          );
          setTimeout(() => this.loadFindings(), 3000);
        },
        error: (err) => {
          this.isTriggering.set(false);
          this.triggerStatus.set(
            `Błąd uruchamiania analizy: ${err.message ?? "nieznany"}`,
          );
        },
      });
  }

  onFilterChange(field: string, value: string): void {
    if (field === "gapType") this.filterGapType.set(value);
    if (field === "severity") this.filterSeverity.set(value);
    this.pageIndex.set(0);
    this.loadFindings();
  }

  toggleExpand(row: GapFinding): void {
    this.expandedElement.set(this.expandedElement() === row ? null : row);
  }

  onPageChange(event: PageEvent): void {
    this.pageIndex.set(event.pageIndex);
    this.pageSize.set(event.pageSize);
    this.loadFindings();
  }

  gapTypeLabel(type: string): string {
    const labels: Record<string, string> = {
      missing: "Brakujące",
      different: "Różne",
      extra: "Nadmiarowe",
      inconsistent: "Niespójne",
    };
    return labels[type] ?? type;
  }

  severityLabel(sev: string): string {
    const labels: Record<string, string> = {
      critical: "Krytyczny",
      warning: "Ostrzeżenie",
      info: "Info",
    };
    return labels[sev] ?? sev;
  }

  generateSkeleton(finding: GapFinding, event: Event): void {
    event.stopPropagation();
    this.skeletonGenerating.set(finding.id);
    this.gapService
      .generateSkeleton(this.projectId, finding.id, "python")
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (resp) => {
          this.skeletonPreview.update((prev) => ({
            ...prev,
            [finding.id]: resp,
          }));
          this.skeletonGenerating.set(null);
        },
        error: () => this.skeletonGenerating.set(null),
      });
  }

  copySkeleton(code: string): void {
    navigator.clipboard.writeText(code);
  }
}
