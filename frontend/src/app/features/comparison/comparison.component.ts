import { Component, DestroyRef, OnInit, inject, signal, computed } from "@angular/core";
import { CommonModule } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatSelectModule } from "@angular/material/select";
import { MatTableModule } from "@angular/material/table";
import { MatChipsModule } from "@angular/material/chips";
import { NavbarComponent } from "../../shared/components/navbar.component";
import { FooterComponent } from "../../shared/components/footer.component";
import {
  GapAnalysisService,
  ComplianceSnapshot,
  ComparisonResponse,
  TrendResponse,
  FindingDiff,
} from "../gap-analysis/services/gap-analysis.service";

@Component({
  selector: "app-comparison",
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    MatTableModule,
    MatChipsModule,
    NavbarComponent,
    FooterComponent,
  ],
  template: `
    <div class="cmp-page">
      <app-navbar activeLink="projects" />
      <main class="cmp-content" id="main-content" tabindex="-1">
        <a mat-button routerLink="/projects" class="back-link">
          <mat-icon>arrow_back</mat-icon>
          Wróć do projektów
        </a>

        <div class="header-row">
          <h1 class="page-title">Porównanie wersji analizy</h1>
          <button
            mat-raised-button
            color="primary"
            (click)="createSnapshot()"
            [disabled]="isCreating()"
          >
            <mat-icon>camera</mat-icon>
            Utwórz snapshot
          </button>
        </div>

        @if (loading()) {
          <mat-progress-spinner mode="indeterminate" />
        } @else {
          <!-- Snapshot selector -->
          <div class="selector-row">
            <mat-form-field appearance="outline" class="snapshot-select">
              <mat-label>Wersja 1 (wcześniejsza)</mat-label>
              <mat-select
                [(value)]="v1Id"
                (selectionChange)="onSnapshotChange()"
              >
                @for (s of snapshots(); track s.id) {
                  <mat-option [value]="s.id">
                    {{ s.label || snapshotLabel(s) }} — score: {{ s.score }}
                  </mat-option>
                }
              </mat-select>
            </mat-form-field>

            <mat-form-field appearance="outline" class="snapshot-select">
              <mat-label>Wersja 2 (nowsza)</mat-label>
              <mat-select
                [(value)]="v2Id"
                (selectionChange)="onSnapshotChange()"
              >
                @for (s of snapshots(); track s.id) {
                  <mat-option [value]="s.id">
                    {{ s.label || snapshotLabel(s) }} — score: {{ s.score }}
                  </mat-option>
                }
              </mat-select>
            </mat-form-field>

            <button
              mat-raised-button
              color="primary"
              (click)="loadComparison()"
              [disabled]="!v1Id || !v2Id || v1Id === v2Id"
            >
              <mat-icon>compare_arrows</mat-icon>
              Porównaj
            </button>
          </div>

          <!-- Comparison result -->
          @if (comparison()) {
            @let cmp = comparison()!;
            @let diff = cmp.snapshotDiff;

            <!-- Score delta card -->
            <div class="score-card" [class.improved]="diff.direction === 'improved'" [class.regressed]="diff.direction === 'regressed'">
              <div class="score-block">
                <span class="score-label">Wersja 1</span>
                <span class="score-value">{{ diff.v1Score }}</span>
              </div>
              <div class="delta-block">
                <mat-icon>{{
                  diff.direction === "improved"
                    ? "trending_up"
                    : diff.direction === "regressed"
                      ? "trending_down"
                      : "trending_flat"
                }}</mat-icon>
                <span class="delta-value">
                  {{ diff.scoreDelta > 0 ? "+" : "" }}{{ diff.scoreDelta }}
                </span>
              </div>
              <div class="score-block">
                <span class="score-label">Wersja 2</span>
                <span class="score-value">{{ diff.v2Score }}</span>
              </div>
            </div>

            <!-- Summary chips -->
            <div class="summary-chips">
              <mat-chip-set>
                <mat-chip>
                  <mat-icon matChipAvatar class="chip-green">check_circle</mat-icon>
                  Naprawione: {{ cmp.summary["fixed"] || 0 }}
                </mat-chip>
                <mat-chip>
                  <mat-icon matChipAvatar class="chip-red">add_circle</mat-icon>
                  Nowe: {{ cmp.summary["new"] || 0 }}
                </mat-chip>
                <mat-chip>
                  <mat-icon matChipAvatar class="chip-grey">remove</mat-icon>
                  Bez zmian: {{ cmp.summary["unchanged"] || 0 }}
                </mat-chip>
                <mat-chip>
                  <mat-icon matChipAvatar class="chip-orange">warning</mat-icon>
                  Pogorszone: {{ cmp.summary["worsened"] || 0 }}
                </mat-chip>
              </mat-chip-set>
            </div>

            <!-- Gap type deltas -->
            <div class="deltas-grid">
              <div class="delta-item">
                <span class="delta-label">Missing</span>
                <span class="delta-num" [class.positive]="diff.missingDelta < 0" [class.negative]="diff.missingDelta > 0">
                  {{ diff.missingDelta > 0 ? "+" : "" }}{{ diff.missingDelta }}
                </span>
              </div>
              <div class="delta-item">
                <span class="delta-label">Different</span>
                <span class="delta-num" [class.positive]="diff.differentDelta < 0" [class.negative]="diff.differentDelta > 0">
                  {{ diff.differentDelta > 0 ? "+" : "" }}{{ diff.differentDelta }}
                </span>
              </div>
              <div class="delta-item">
                <span class="delta-label">Extra</span>
                <span class="delta-num" [class.positive]="diff.extraDelta < 0" [class.negative]="diff.extraDelta > 0">
                  {{ diff.extraDelta > 0 ? "+" : "" }}{{ diff.extraDelta }}
                </span>
              </div>
              <div class="delta-item">
                <span class="delta-label">Inconsistent</span>
                <span class="delta-num" [class.positive]="diff.inconsistentDelta < 0" [class.negative]="diff.inconsistentDelta > 0">
                  {{ diff.inconsistentDelta > 0 ? "+" : "" }}{{ diff.inconsistentDelta }}
                </span>
              </div>
              <div class="delta-item">
                <span class="delta-label">Coverage</span>
                <span class="delta-num" [class.positive]="diff.coverageDelta > 0" [class.negative]="diff.coverageDelta < 0">
                  {{ diff.coverageDelta > 0 ? "+" : "" }}{{ diff.coverageDelta }}%
                </span>
              </div>
            </div>

            <!-- Finding diffs table -->
            @if (cmp.findingDiffs.length > 0) {
              <h3 class="section-title">Szczegóły luk</h3>
              <table mat-table [dataSource]="cmp.findingDiffs" class="diff-table">
                <caption class="visually-hidden">Porównanie luk między wersjami analizy</caption>
                <ng-container matColumnDef="status">
                  <th mat-header-cell *matHeaderCellDef scope="col">Status</th>
                  <td mat-cell *matCellDef="let d">
                    <mat-chip-set>
                      <mat-chip [class.chip-green]="d.status === 'fixed'"
                                [class.chip-red]="d.status === 'new'"
                                [class.chip-grey]="d.status === 'unchanged'"
                                [class.chip-orange]="d.status === 'worsened'">
                        {{ statusLabel(d.status) }}
                      </mat-chip>
                    </mat-chip-set>
                  </td>
                </ng-container>

                <ng-container matColumnDef="gapType">
                  <th mat-header-cell *matHeaderCellDef scope="col">Typ luki</th>
                  <td mat-cell *matCellDef="let d">{{ d.gapType }}</td>
                </ng-container>

                <ng-container matColumnDef="requirement">
                  <th mat-header-cell *matHeaderCellDef scope="col">Wymaganie</th>
                  <td mat-cell *matCellDef="let d">{{ d.requirementText || '—' }}</td>
                </ng-container>

                <ng-container matColumnDef="v1Severity">
                  <th mat-header-cell *matHeaderCellDef scope="col">V1 Severity</th>
                  <td mat-cell *matCellDef="let d">{{ d.v1Severity || '—' }}</td>
                </ng-container>

                <ng-container matColumnDef="v2Severity">
                  <th mat-header-cell *matHeaderCellDef scope="col">V2 Severity</th>
                  <td mat-cell *matCellDef="let d">{{ d.v2Severity || '—' }}</td>
                </ng-container>

                <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
                <tr mat-row *matRowDef="let row; columns: displayedColumns"></tr>
              </table>
            }
          }

          <!-- Trend section -->
          @if (trend().points.length > 0) {
            <h3 class="section-title">Trend compliance</h3>
            <div class="trend-chart">
              @for (p of trend().points; track p.snapshotId) {
                <div class="trend-bar-wrapper">
                  <div class="trend-bar" [style.height.%]="p.score">
                    <span class="trend-score">{{ p.score }}</span>
                  </div>
                  <span class="trend-label">{{ p.label || trendDate(p) }}</span>
                </div>
              }
            </div>
          }

          @if (snapshots().length < 2) {
            <div class="empty-state">
              <mat-icon>info</mat-icon>
              <p>Utwórz co najmniej 2 snapshoty, aby porównać wersje analizy.</p>
            </div>
          }
        }
      </main>
      <app-footer />
    </div>
  `,
  styles: [`
    .cmp-page { min-height: 100vh; display: flex; flex-direction: column; }
    .cmp-content { max-width: 1200px; width: 100%; margin: 0 auto; padding: 24px; flex: 1; }
    .back-link { margin-bottom: 16px; }
    .header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
    .page-title { font-size: 24px; margin: 0; }
    .selector-row { display: flex; gap: 16px; align-items: center; margin-bottom: 24px; flex-wrap: wrap; }
    .snapshot-select { flex: 1; min-width: 250px; }
    .score-card {
      display: flex; justify-content: space-around; align-items: center;
      padding: 24px; border-radius: 12px; margin-bottom: 16px;
      background: #f5f5f5; border: 2px solid #e0e0e0;
    }
    .score-card.improved { background: #e8f5e9; border-color: #4caf50; }
    .score-card.regressed { background: #ffebee; border-color: #f44336; }
    .score-block { display: flex; flex-direction: column; align-items: center; }
    .score-label { font-size: 12px; color: #666; }
    .score-value { font-size: 36px; font-weight: 700; }
    .delta-block { display: flex; align-items: center; gap: 8px; }
    .delta-value { font-size: 20px; font-weight: 600; }
    .summary-chips { margin-bottom: 24px; }
    .chip-green { color: #4caf50; }
    .chip-red { color: #f44336; }
    .chip-grey { color: #9e9e9e; }
    .chip-orange { color: #ff9800; }
    .deltas-grid {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 12px; margin-bottom: 24px;
    }
    .delta-item {
      display: flex; flex-direction: column; align-items: center;
      padding: 12px; border-radius: 8px; background: #fafafa;
    }
    .delta-label { font-size: 12px; color: #666; }
    .delta-num { font-size: 20px; font-weight: 600; }
    .delta-num.positive { color: #4caf50; }
    .delta-num.negative { color: #f44336; }
    .section-title { font-size: 18px; margin: 24px 0 12px; }
    .diff-table { width: 100%; }
    .trend-chart {
      display: flex; align-items: flex-end; gap: 8px; height: 200px;
      padding: 16px; background: #fafafa; border-radius: 8px; overflow-x: auto;
    }
    .trend-bar-wrapper {
      display: flex; flex-direction: column; align-items: center;
      min-width: 60px; height: 100%; justify-content: flex-end;
    }
    .trend-bar {
      width: 100%; min-height: 4px; background: #3f51b5; border-radius: 4px 4px 0 0;
      display: flex; align-items: flex-start; justify-content: center;
      color: white; font-size: 10px; padding-top: 4px;
    }
    .trend-label { font-size: 10px; color: #666; margin-top: 4px; text-align: center; }
    .empty-state {
      text-align: center; padding: 48px; color: #666;
      display: flex; flex-direction: column; align-items: center; gap: 8px;
    }
    .empty-state mat-icon { font-size: 48px; width: 48px; height: 48px; }
  `],
})
export class ComparisonComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly gapService = inject(GapAnalysisService);
  private readonly destroyRef = inject(DestroyRef);

  readonly projectId = signal<string>("");
  readonly loading = signal(true);
  readonly isCreating = signal(false);
  readonly snapshots = signal<ComplianceSnapshot[]>([]);
  readonly comparison = signal<ComparisonResponse | null>(null);
  readonly trend = signal<TrendResponse>({ points: [] });

  v1Id = "";
  v2Id = "";

  readonly displayedColumns = ["status", "gapType", "requirement", "v1Severity", "v2Severity"];

  ngOnInit(): void {
    const pid = this.route.snapshot.paramMap.get("projectId") ?? "";
    this.projectId.set(pid);
    this.loadData();
  }

  loadData(): void {
    this.loading.set(true);
    this.gapService.getSnapshots(this.projectId()).pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (snaps) => {
          this.snapshots.set(snaps);
          if (snaps.length >= 2) {
            this.v1Id = snaps[snaps.length - 1].id;
            this.v2Id = snaps[0].id;
          }
          this.loading.set(false);
          this.loadTrend();
        },
        error: () => this.loading.set(false),
      });
  }

  loadTrend(): void {
    this.gapService.getTrend(this.projectId()).pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({ next: (t) => this.trend.set(t) });
  }

  loadComparison(): void {
    if (!this.v1Id || !this.v2Id || this.v1Id === this.v2Id) return;
    this.gapService.compareVersions(this.projectId(), this.v1Id, this.v2Id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({ next: (c) => this.comparison.set(c) });
  }

  onSnapshotChange(): void {
    // auto-load when both selected
  }

  createSnapshot(): void {
    this.isCreating.set(true);
    const label = `Snapshot ${new Date().toLocaleString("pl-PL")}`;
    this.gapService.createSnapshot(this.projectId(), label)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.isCreating.set(false);
          this.loadData();
        },
        error: () => this.isCreating.set(false),
      });
  }

  snapshotLabel(s: ComplianceSnapshot): string {
    if (s.label) return s.label;
    return new Date(s.createdAt).toLocaleDateString("pl-PL");
  }

  trendDate(p: { timestamp: string | null }): string {
    if (!p.timestamp) return "—";
    return new Date(p.timestamp).toLocaleDateString("pl-PL");
  }

  statusLabel(status: string): string {
    const labels: Record<string, string> = {
      fixed: "Naprawione",
      new: "Nowe",
      unchanged: "Bez zmian",
      worsened: "Pogorszone",
    };
    return labels[status] ?? status;
  }
}
