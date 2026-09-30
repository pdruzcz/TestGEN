import {
  Component,
  DestroyRef,
  OnInit,
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
  ComplianceService,
  ComplianceScore,
  ModuleScore,
  FunctionScore,
} from "./services/compliance.service";

@Component({
  selector: "app-compliance",
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
    <div class="comp-page">
      <app-navbar activeLink="projects" />
      <main class="comp-content" id="main-content" tabindex="-1">
        <a mat-button routerLink="/projects" class="back-link">
          <mat-icon>arrow_back</mat-icon>
          Wróć do projektów
        </a>

        <div class="header-row">
          <h1 class="page-title">Compliance</h1>
          <button
            mat-stroked-button
            (click)="exportReport()"
            [disabled]="isExporting()"
          >
            <mat-icon>{{ isExporting() ? 'hourglass_empty' : 'download' }}</mat-icon>
            Eksportuj CSV
          </button>
        </div>

        @if (isLoading()) {
          <mat-spinner diameter="40" aria-label="Ładowanie" />
        } @else {
          @if (projectScore()) {
            <div class="score-section">
              <div class="gauge-wrapper">
                <div class="gauge" [class]="'gauge-' + scoreLevel()">
                  <span class="gauge-value">{{ projectScore()!.score }}%</span>
                </div>
                <span class="gauge-label">Wynik compliance</span>
              </div>

              <div class="breakdown-grid">
                @for (key of breakdownKeys(); track key) {
                  <div class="breakdown-card" [class]="'bc-' + key">
                    <span class="bc-value">{{ projectScore()!.breakdown[key] }}</span>
                    <span class="bc-label">{{ gapTypeLabel(key) }}</span>
                  </div>
                }
                <div class="breakdown-card bc-total">
                  <span class="bc-value">{{ projectScore()!.totalFindings }}</span>
                  <span class="bc-label">Razem</span>
                </div>
              </div>
            </div>
          }

          @if (moduleScores().length > 0) {
            <h2 class="section-title">Wyniki per moduł</h2>
            <table mat-table [dataSource]="moduleScores()" class="scores-table">
              <caption class="visually-hidden">Wyniki zgodności per moduł</caption>
              <ng-container matColumnDef="file">
                <th mat-header-cell *matHeaderCellDef scope="col">Plik</th>
                <td mat-cell *matCellDef="let m">{{ m.filePath }}</td>
              </ng-container>

              <ng-container matColumnDef="score">
                <th mat-header-cell *matHeaderCellDef scope="col">Wynik (%)</th>
                <td mat-cell *matCellDef="let m">
                  <div class="score-bar">
                    <div
                      class="score-fill"
                      [style.width.%]="m.score"
                      [class]="'fill-' + scoreClass(m.score)"
                    ></div>
                    <span class="score-text">{{ m.score.toFixed(1) }}</span>
                  </div>
                </td>
              </ng-container>

              <ng-container matColumnDef="findings">
                <th mat-header-cell *matHeaderCellDef scope="col">Luk</th>
                <td mat-cell *matCellDef="let m">{{ m.totalFindings }}</td>
              </ng-container>

              <ng-container matColumnDef="breakdown">
                <th mat-header-cell *matHeaderCellDef scope="col">Szczegóły</th>
                <td mat-cell *matCellDef="let m" class="breakdown-cell">
                  <span class="mini-chip chip-missing" [class.hidden]="!m.breakdown['missing']">
                    {{ m.breakdown['missing'] || 0 }} M
                  </span>
                  <span class="mini-chip chip-different" [class.hidden]="!m.breakdown['different']">
                    {{ m.breakdown['different'] || 0 }} R
                  </span>
                  <span class="mini-chip chip-extra" [class.hidden]="!m.breakdown['extra']">
                    {{ m.breakdown['extra'] || 0 }} N
                  </span>
                  <span class="mini-chip chip-inconsistent" [class.hidden]="!m.breakdown['inconsistent']">
                    {{ m.breakdown['inconsistent'] || 0 }} NS
                  </span>
                </td>
              </ng-container>

              <tr mat-header-row *matHeaderRowDef="moduleColumns"></tr>
              <tr mat-row *matRowDef="let row; columns: moduleColumns"></tr>
            </table>
          }

          @if (functionScores().length > 0) {
            <h2 class="section-title">Wyniki per funkcja</h2>
            <table mat-table [dataSource]="functionScores()" class="scores-table">
              <caption class="visually-hidden">Wyniki zgodności per funkcja</caption>
              <ng-container matColumnDef="entity">
                <th mat-header-cell *matHeaderCellDef scope="col">Byt kodu</th>
                <td mat-cell *matCellDef="let f">
                  <div class="entity-name">{{ f.entityName || f.codeEntityId }}</div>
                  @if (f.filePath) {
                    <div class="entity-file">{{ f.filePath }}</div>
                  }
                </td>
              </ng-container>

              <ng-container matColumnDef="score">
                <th mat-header-cell *matHeaderCellDef scope="col">Wynik (%)</th>
                <td mat-cell *matCellDef="let f">
                  <div class="score-bar">
                    <div
                      class="score-fill"
                      [style.width.%]="f.score"
                      [class]="'fill-' + scoreClass(f.score)"
                    ></div>
                    <span class="score-text">{{ f.score.toFixed(1) }}</span>
                  </div>
                </td>
              </ng-container>

              <ng-container matColumnDef="findings">
                <th mat-header-cell *matHeaderCellDef scope="col">Luk</th>
                <td mat-cell *matCellDef="let f">{{ f.totalFindings }}</td>
              </ng-container>

              <tr mat-header-row *matHeaderRowDef="functionColumns"></tr>
              <tr mat-row *matRowDef="let row; columns: functionColumns"></tr>
            </table>
          }

          @if (projectScore() && projectScore()!.totalFindings === 0) {
            <div class="empty-state">
              <mat-icon>verified</mat-icon>
              <p>Brak luk — pełna zgodność z dokumentacją.</p>
            </div>
          }
        }
      </main>
      <app-footer />
    </div>
  `,
  styles: [
    `
      .comp-page {
        min-height: 100vh;
        background: #f7f8fa;
        display: flex;
        flex-direction: column;
      }
      .comp-content {
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
      .score-section {
        display: flex;
        gap: 32px;
        align-items: center;
        flex-wrap: wrap;
        background: white;
        border-radius: 12px;
        padding: 24px;
        border: 1px solid #e5e7eb;
      }
      .gauge-wrapper {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
      }
      .gauge {
        width: 120px;
        height: 120px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 8px solid;
      }
      .gauge-high {
        border-color: #16a34a;
        background: #dcfce7;
      }
      .gauge-medium {
        border-color: #f59e0b;
        background: #fef3c7;
      }
      .gauge-low {
        border-color: #ef4444;
        background: #fee2e2;
      }
      .gauge-value {
        font-size: 28px;
        font-weight: 700;
      }
      .gauge-label {
        font-size: 14px;
        color: #6b7280;
      }
      .breakdown-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
        gap: 12px;
        flex: 1;
        min-width: 300px;
      }
      .breakdown-card {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 12px;
        border-radius: 8px;
        background: #f9fafb;
      }
      .bc-value {
        font-size: 24px;
        font-weight: 700;
      }
      .bc-label {
        font-size: 12px;
        color: #6b7280;
        margin-top: 2px;
      }
      .bc-missing { border-left: 3px solid #ef4444; }
      .bc-different { border-left: 3px solid #f59e0b; }
      .bc-extra { border-left: 3px solid #eab308; }
      .bc-inconsistent { border-left: 3px solid #a855f7; }
      .bc-total { border-left: 3px solid #3b82f6; }
      .section-title {
        font-size: 20px;
        font-weight: 600;
        color: #1a1a1a;
        margin: 8px 0 0 0;
      }
      .scores-table {
        width: 100%;
        background: white;
        border-radius: 8px;
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
        transition: width 0.3s;
      }
      .fill-high { background: #22c55e; }
      .fill-medium { background: #f59e0b; }
      .fill-low { background: #ef4444; }
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
      .breakdown-cell {
        display: flex;
        gap: 4px;
      }
      .mini-chip {
        padding: 1px 6px;
        border-radius: 8px;
        font-size: 10px;
        font-weight: 600;
      }
      .mini-chip.hidden { display: none; }
      .chip-missing { background: #fef2f2; color: #991b1b; }
      .chip-different { background: #fffbeb; color: #92400e; }
      .chip-extra { background: #fefce8; color: #854d0e; }
      .chip-inconsistent { background: #faf5ff; color: #6b21a8; }
      .entity-name {
        font-weight: 600;
        font-size: 13px;
      }
      .entity-file {
        font-size: 11px;
        color: #6b7280;
        font-family: monospace;
      }
      .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 48px;
        color: #16a34a;
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
export class ComplianceComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly complianceService = inject(ComplianceService);

  readonly projectId = this.route.snapshot.paramMap.get("projectId") ?? "";

  readonly isLoading = signal(true);
  readonly isExporting = signal(false);
  readonly projectScore = signal<ComplianceScore | null>(null);
  readonly moduleScores = signal<ModuleScore[]>([]);
  readonly functionScores = signal<FunctionScore[]>([]);

  readonly moduleColumns = ["file", "score", "findings", "breakdown"];
  readonly functionColumns = ["entity", "score", "findings"];

  readonly breakdownKeys = signal<string[]>([
    "missing",
    "different",
    "extra",
    "inconsistent",
  ]);

  ngOnInit(): void {
    this.loadAll();
  }

  loadAll(): void {
    this.isLoading.set(true);
    this.complianceService
      .getProjectScore(this.projectId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (score) => {
          this.projectScore.set(score);
          this.isLoading.set(false);
        },
        error: () => this.isLoading.set(false),
      });

    this.complianceService
      .getModuleScores(this.projectId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (scores) => this.moduleScores.set(scores),
        error: () => {},
      });

    this.complianceService
      .getFunctionScores(this.projectId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (scores) => this.functionScores.set(scores),
        error: () => {},
      });
  }

  exportReport(): void {
    this.isExporting.set(true);
    this.complianceService
      .exportReport(this.projectId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (resp) => {
          this.isExporting.set(false);
          const blob = new Blob([resp.csv], { type: "text/csv;charset=utf-8" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `compliance-${this.projectId}.csv`;
          a.click();
          URL.revokeObjectURL(url);
        },
        error: () => this.isExporting.set(false),
      });
  }

  scoreLevel(): string {
    const s = this.projectScore()?.score ?? 0;
    if (s >= 80) return "high";
    if (s >= 50) return "medium";
    return "low";
  }

  scoreClass(score: number): string {
    if (score >= 80) return "high";
    if (score >= 50) return "medium";
    return "low";
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
}
