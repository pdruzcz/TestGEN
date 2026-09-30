import {
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  signal,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatTableModule } from "@angular/material/table";
import { MatTooltipModule } from "@angular/material/tooltip";
import { NavbarComponent } from "../../shared/components/navbar.component";
import { FooterComponent } from "../../shared/components/footer.component";
import {
  Recommendation,
  RecommendationSummary,
  RecommendationsService,
} from "./services/recommendations.service";

@Component({
  selector: "app-recommendations",
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatTableModule,
    MatTooltipModule,
    NavbarComponent,
    FooterComponent,
  ],
  template: `
    <div class="rec-page">
      <app-navbar activeLink="projects" />
      <main class="rec-content" id="main-content" tabindex="-1">
        <a mat-button routerLink="/projects" class="back-link">
          <mat-icon>arrow_back</mat-icon>
          Wróć do projektów
        </a>

        <div class="header-row">
          <h1 class="page-title">Rekomendacje</h1>
          <button
            mat-raised-button
            color="primary"
            (click)="generate()"
            [disabled]="isGenerating()"
          >
            <mat-icon>{{
              isGenerating() ? "hourglass_empty" : "auto_fix_high"
            }}</mat-icon>
            {{ isGenerating() ? "Generowanie..." : "Generuj rekomendacje" }}
          </button>
        </div>

        @if (isLoading()) {
          <mat-spinner diameter="40" aria-label="Ładowanie" />
        } @else {
          @if (summary()) {
            <div class="summary-section">
              <div class="summary-card">
                <span class="summary-value">{{ summary()!.total }}</span>
                <span class="summary-label">Razem</span>
              </div>
              <div class="summary-card pri-p1">
                <span class="summary-value">{{
                  summary()!.by_priority["P1"] || 0
                }}</span>
                <span class="summary-label">P1 — Krytyczne</span>
              </div>
              <div class="summary-card pri-p2">
                <span class="summary-value">{{
                  summary()!.by_priority["P2"] || 0
                }}</span>
                <span class="summary-label">P2 — Wysokie</span>
              </div>
              <div class="summary-card pri-p3">
                <span class="summary-value">{{
                  summary()!.by_priority["P3"] || 0
                }}</span>
                <span class="summary-label">P3 — Średnie</span>
              </div>
              <div class="summary-card pri-p4">
                <span class="summary-value">{{
                  summary()!.by_priority["P4"] || 0
                }}</span>
                <span class="summary-label">P4 — Niskie</span>
              </div>
              <div class="summary-card conf-card">
                <span class="summary-value"
                  >{{ (summary()!.avg_confidence * 100).toFixed(0) }}%</span
                >
                <span class="summary-label">Śr. pewność</span>
              </div>
              @if (summary()!.low_confidence_count > 0) {
                <div class="summary-card low-conf-card">
                  <span class="summary-value">{{
                    summary()!.low_confidence_count
                  }}</span>
                  <span class="summary-label">Niska pewność</span>
                </div>
              }
            </div>
          }

          @if (recommendations().length > 0) {
            <h2 class="section-title">Lista rekomendacji</h2>
            <table mat-table [dataSource]="recommendations()" class="rec-table">
              <caption class="visually-hidden">Lista rekomendacji</caption>
              <ng-container matColumnDef="priority">
                <th mat-header-cell *matHeaderCellDef scope="col">Priorytet</th>
                <td mat-cell *matCellDef="let r">
                  <span
                    class="pri-chip"
                    [class]="'pri-' + r.priority.toLowerCase()"
                  >
                    {{ r.priority }}
                  </span>
                </td>
              </ng-container>

              <ng-container matColumnDef="source">
                <th mat-header-cell *matHeaderCellDef scope="col">Źródło</th>
                <td mat-cell *matCellDef="let r">
                  <span class="src-chip" [class]="'src-' + r.source_type">
                    {{ sourceLabel(r.source_type) }}
                  </span>
                </td>
              </ng-container>

              <ng-container matColumnDef="title">
                <th mat-header-cell *matHeaderCellDef scope="col">Tytuł</th>
                <td mat-cell *matCellDef="let r" class="title-cell">
                  <div class="title-text">{{ r.title }}</div>
                  <div class="desc-text">{{ r.description }}</div>
                </td>
              </ng-container>

              <ng-container matColumnDef="confidence">
                <th mat-header-cell *matHeaderCellDef scope="col">Pewność</th>
                <td mat-cell *matCellDef="let r">
                  <div class="conf-bar">
                    <div
                      class="conf-fill"
                      [class]="'conf-' + confidenceLevel(r.confidence)"
                      [style.width.%]="r.confidence * 100"
                    ></div>
                  </div>
                  <span
                    class="conf-value"
                    [class]="'conf-text-' + confidenceLevel(r.confidence)"
                  >
                    {{ (r.confidence * 100).toFixed(0) }}%
                  </span>
                </td>
              </ng-container>

              <ng-container matColumnDef="suggestion">
                <th mat-header-cell *matHeaderCellDef scope="col">Sugestia</th>
                <td mat-cell *matCellDef="let r">
                  @if (r.suggestion) {
                    <span
                      matTooltip="{{ r.suggestion }}"
                      class="suggestion-text"
                    >
                      {{ r.suggestion }}
                    </span>
                  } @else {
                    <span class="no-suggestion">—</span>
                  }
                </td>
              </ng-container>

              <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
              <tr mat-row *matRowDef="let row; columns: displayedColumns"></tr>
            </table>
          }

          @if (summary() && summary()!.total === 0) {
            <div class="empty-state">
              <mat-icon>lightbulb_outline</mat-icon>
              <p>
                Brak rekomendacji. Kliknij „Generuj rekomendacje", aby utworzyć.
              </p>
            </div>
          }
        }
      </main>
      <app-footer />
    </div>
  `,
  styles: [
    `
      .rec-page {
        min-height: 100vh;
        background: #f7f8fa;
        display: flex;
        flex-direction: column;
      }
      .rec-content {
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
      .summary-section {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
      }
      .summary-card {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 16px 24px;
        border-radius: 12px;
        background: white;
        border: 1px solid #e5e7eb;
        min-width: 120px;
      }
      .summary-value {
        font-size: 28px;
        font-weight: 700;
        color: #1a1a1a;
      }
      .summary-label {
        font-size: 12px;
        color: #6b7280;
        margin-top: 4px;
      }
      .pri-p1 {
        border-left: 4px solid #dc2626;
      }
      .pri-p2 {
        border-left: 4px solid #f59e0b;
      }
      .pri-p3 {
        border-left: 4px solid #3b82f6;
      }
      .pri-p4 {
        border-left: 4px solid #6b7280;
      }
      .conf-card {
        border-left: 4px solid #8b5cf6;
      }
      .low-conf-card {
        border-left: 4px solid #ef4444;
      }
      .section-title {
        font-size: 20px;
        font-weight: 600;
        color: #1a1a1a;
        margin: 8px 0 0 0;
      }
      .rec-table {
        width: 100%;
        background: white;
        border-radius: 8px;
      }
      .pri-chip {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 24px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 700;
      }
      .pri-p1 {
        background: #fef2f2;
        color: #991b1b;
      }
      .pri-p2 {
        background: #fffbeb;
        color: #92400e;
      }
      .pri-p3 {
        background: #eff6ff;
        color: #1e40af;
      }
      .pri-p4 {
        background: #f3f4f6;
        color: #4b5563;
      }
      .src-chip {
        padding: 2px 8px;
        border-radius: 8px;
        font-size: 11px;
        font-weight: 600;
        white-space: nowrap;
      }
      .src-gap_finding {
        background: #faf5ff;
        color: #6b21a8;
      }
      .src-code_error {
        background: #fef2f2;
        color: #991b1b;
      }
      .title-cell {
        max-width: 400px;
      }
      .title-text {
        font-size: 13px;
        font-weight: 600;
        color: #1a1a1a;
      }
      .desc-text {
        font-size: 12px;
        color: #6b7280;
        margin-top: 2px;
      }
      .conf-bar {
        width: 60px;
        height: 6px;
        background: #e5e7eb;
        border-radius: 3px;
        overflow: hidden;
        display: inline-block;
        vertical-align: middle;
        margin-right: 6px;
      }
      .conf-fill {
        height: 100%;
        border-radius: 3px;
      }
      .conf-high {
        background: #16a34a;
      }
      .conf-medium {
        background: #f59e0b;
      }
      .conf-low {
        background: #ef4444;
      }
      .conf-value {
        font-size: 12px;
        font-weight: 600;
      }
      .conf-text-high {
        color: #16a34a;
      }
      .conf-text-medium {
        color: #f59e0b;
      }
      .conf-text-low {
        color: #ef4444;
      }
      .suggestion-text {
        font-size: 12px;
        color: #4b5563;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }
      .no-suggestion {
        color: #d1d5db;
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
    `,
  ],
})
export class RecommendationsComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly recService = inject(RecommendationsService);

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  readonly isLoading = signal(true);
  readonly isGenerating = signal(false);
  readonly recommendations = signal<Recommendation[]>([]);
  readonly summary = signal<RecommendationSummary | null>(null);

  readonly displayedColumns = [
    "priority",
    "source",
    "title",
    "confidence",
    "suggestion",
  ];

  ngOnInit(): void {
    this.loadRecommendations();
  }

  loadRecommendations(): void {
    this.isLoading.set(true);
    this.recService
      .getRecommendations(this.projectId(), { size: 100 })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (resp) => {
          this.recommendations.set(resp.recommendations);
          this.summary.set(resp.summary);
          this.isLoading.set(false);
        },
        error: () => this.isLoading.set(false),
      });
  }

  generate(): void {
    this.isGenerating.set(true);
    this.recService
      .generate(this.projectId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.isGenerating.set(false);
          setTimeout(() => this.loadRecommendations(), 2000);
        },
        error: () => {
          this.isGenerating.set(false);
          this.loadRecommendations();
        },
      });
  }

  sourceLabel(src: string): string {
    const labels: Record<string, string> = {
      gap_finding: "Luka",
      code_error: "Błąd kodu",
    };
    return labels[src] ?? src;
  }

  confidenceLevel(conf: number): string {
    if (conf >= 0.7) return "high";
    if (conf >= 0.5) return "medium";
    return "low";
  }
}
