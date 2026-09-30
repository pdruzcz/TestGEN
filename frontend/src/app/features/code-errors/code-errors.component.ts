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
  CodeError,
  CodeErrorsService,
  CodeErrorSummary,
} from "./services/code-errors.service";

@Component({
  selector: "app-code-errors",
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
    <div class="ce-page">
      <app-navbar activeLink="projects" />
      <main class="ce-content" id="main-content" tabindex="-1">
        <a mat-button routerLink="/projects" class="back-link">
          <mat-icon>arrow_back</mat-icon>
          Wróć do projektów
        </a>

        <div class="header-row">
          <h1 class="page-title">Błędy kodu</h1>
          <button
            mat-raised-button
            color="primary"
            (click)="runScan()"
            [disabled]="isScanning()"
          >
            <mat-icon>{{
              isScanning() ? "hourglass_empty" : "radar"
            }}</mat-icon>
            {{ isScanning() ? "Skanowanie..." : "Skanuj kod" }}
          </button>
        </div>

        @if (isLoading()) {
          <mat-spinner diameter="40" aria-label="Ładowanie" />
        } @else {
          @if (summary()) {
            <div class="summary-section">
              <div class="summary-card">
                <span class="summary-value">{{ summary()!.totalErrors }}</span>
                <span class="summary-label">Razem błędów</span>
              </div>
              @for (cat of categoryKeys(); track cat) {
                <div class="summary-card" [class]="'cat-' + cat">
                  <span class="summary-value">{{ categoryCount(cat) }}</span>
                  <span class="summary-label">{{ categoryLabel(cat) }}</span>
                </div>
              }
              <div class="summary-card sev-critical">
                <span class="summary-value">{{
                  summary()!.bySeverity["critical"] || 0
                }}</span>
                <span class="summary-label">Krytyczne</span>
              </div>
              <div class="summary-card sev-warning">
                <span class="summary-value">{{
                  summary()!.bySeverity["warning"] || 0
                }}</span>
                <span class="summary-label">Ostrzeżenia</span>
              </div>
              <div class="summary-card sev-info">
                <span class="summary-value">{{
                  summary()!.bySeverity["info"] || 0
                }}</span>
                <span class="summary-label">Info</span>
              </div>
            </div>
          }

          @if (errors().length > 0) {
            <h2 class="section-title">Wykryte błędy</h2>
            <table mat-table [dataSource]="errors()" class="errors-table">
              <caption class="visually-hidden">
                Lista wykrytych błędów w kodzie
              </caption>
              <ng-container matColumnDef="severity">
                <th mat-header-cell *matHeaderCellDef scope="col">Poziom</th>
                <td mat-cell *matCellDef="let e">
                  <span class="sev-chip" [class]="'sev-' + e.severity">
                    {{ severityLabel(e.severity) }}
                  </span>
                </td>
              </ng-container>

              <ng-container matColumnDef="category">
                <th mat-header-cell *matHeaderCellDef scope="col">Typ</th>
                <td mat-cell *matCellDef="let e">
                  <span class="cat-chip" [class]="'cat-' + e.category">
                    {{ categoryLabel(e.category) }}
                  </span>
                </td>
              </ng-container>

              <ng-container matColumnDef="message">
                <th mat-header-cell *matHeaderCellDef scope="col">Wiadomość</th>
                <td mat-cell *matCellDef="let e" class="msg-cell">
                  <div class="msg-text">{{ e.message }}</div>
                  @if (e.ruleId) {
                    <div class="rule-id">{{ e.ruleId }}</div>
                  }
                </td>
              </ng-container>

              <ng-container matColumnDef="location">
                <th mat-header-cell *matHeaderCellDef scope="col">
                  Lokalizacja
                </th>
                <td mat-cell *matCellDef="let e" class="loc-cell">
                  @if (e.filePath) {
                    <div class="file-path">{{ e.filePath }}</div>
                  }
                  @if (e.lineStart) {
                    <div class="line-info">
                      L {{ e.lineStart
                      }}{{
                        e.lineEnd !== e.lineStart && e.lineEnd
                          ? "–" + e.lineEnd
                          : ""
                      }}
                    </div>
                  }
                </td>
              </ng-container>

              <ng-container matColumnDef="suggestion">
                <th mat-header-cell *matHeaderCellDef scope="col">Sugestia</th>
                <td mat-cell *matCellDef="let e">
                  @if (e.suggestion) {
                    <span
                      matTooltip="{{ e.suggestion }}"
                      class="suggestion-text"
                    >
                      {{ e.suggestion }}
                    </span>
                  } @else {
                    <span class="no-suggestion">—</span>
                  }
                </td>
              </ng-container>

              <ng-container matColumnDef="actions">
                <th mat-header-cell *matHeaderCellDef scope="col">Akcje</th>
                <td mat-cell *matCellDef="let e">
                  <button
                    mat-icon-button
                    type="button"
                    class="dismiss-btn"
                    matTooltip="Odrzuć jako fałszywy pozytyw — nie wróci przy ponownym skanie"
                    aria-label="Odrzuć znalezisko jako fałszywy pozytyw"
                    (click)="dismiss(e)"
                  >
                    <mat-icon>block</mat-icon>
                  </button>
                </td>
              </ng-container>

              <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
              <tr mat-row *matRowDef="let row; columns: displayedColumns"></tr>
            </table>
          }

          @if (summary() && summary()!.totalErrors === 0) {
            <div class="empty-state">
              <mat-icon>check_circle</mat-icon>
              <p>Brak błędów kodu — kod jest czysty.</p>
            </div>
          }
        }
      </main>
      <app-footer />
    </div>
  `,
  styles: [
    `
      .ce-page {
        min-height: 100vh;
        background: #f7f8fa;
        display: flex;
        flex-direction: column;
      }
      .ce-content {
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
      .cat-syntax {
        border-left: 4px solid #ef4444;
      }
      .cat-logic {
        border-left: 4px solid #f59e0b;
      }
      .cat-semantic {
        border-left: 4px solid #8b5cf6;
      }
      .cat-conformance {
        border-left: 4px solid #3b82f6;
      }
      .cat-dead_code {
        border-left: 4px solid #64748b;
      }
      .sev-critical {
        border-left: 4px solid #ef4444;
      }
      .sev-warning {
        border-left: 4px solid #f59e0b;
      }
      .sev-info {
        border-left: 4px solid #6b7280;
      }
      .section-title {
        font-size: 20px;
        font-weight: 600;
        color: #1a1a1a;
        margin: 8px 0 0 0;
      }
      .errors-table {
        width: 100%;
        background: white;
        border-radius: 8px;
      }
      .sev-chip {
        padding: 2px 8px;
        border-radius: 8px;
        font-size: 11px;
        font-weight: 600;
        white-space: nowrap;
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
      .cat-chip {
        padding: 2px 8px;
        border-radius: 8px;
        font-size: 11px;
        font-weight: 600;
        white-space: nowrap;
      }
      .cat-syntax {
        background: #fef2f2;
        color: #991b1b;
      }
      .cat-logic {
        background: #fffbeb;
        color: #92400e;
      }
      .cat-semantic {
        background: #faf5ff;
        color: #6b21a8;
      }
      .cat-conformance {
        background: #eff6ff;
        color: #1e40af;
      }
      .cat-dead_code {
        background: #f1f5f9;
        color: #334155;
      }
      .dismiss-btn {
        color: #6b7280;
      }
      .msg-cell {
        max-width: 400px;
      }
      .msg-text {
        font-size: 13px;
        color: #1a1a1a;
      }
      .rule-id {
        font-size: 10px;
        color: #6b7280;
        font-family: monospace;
        margin-top: 2px;
      }
      .loc-cell {
        white-space: nowrap;
      }
      .file-path {
        font-size: 12px;
        font-family: monospace;
        color: #374151;
      }
      .line-info {
        font-size: 11px;
        color: #6b7280;
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
export class CodeErrorsComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly codeErrorsService = inject(CodeErrorsService);

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  readonly isLoading = signal(true);
  readonly isScanning = signal(false);
  readonly errors = signal<CodeError[]>([]);
  readonly summary = signal<CodeErrorSummary | null>(null);

  readonly displayedColumns = [
    "severity",
    "category",
    "message",
    "location",
    "suggestion",
    "actions",
  ];

  readonly categoryKeys = signal<string[]>([
    "syntax",
    "logic",
    "semantic",
    "conformance",
    "dead_code",
  ]);

  ngOnInit(): void {
    this.loadErrors();
  }

  loadErrors(): void {
    this.isLoading.set(true);
    this.codeErrorsService
      .getErrors(this.projectId(), { size: 100 })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (resp) => {
          this.errors.set(resp.errors);
          this.summary.set(resp.summary);
          this.isLoading.set(false);
        },
        error: () => this.isLoading.set(false),
      });
  }

  runScan(): void {
    this.isScanning.set(true);
    this.codeErrorsService
      .scan(this.projectId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.isScanning.set(false);
          this.loadErrors();
        },
        error: () => this.isScanning.set(false),
      });
  }

  severityLabel(sev: string): string {
    const labels: Record<string, string> = {
      critical: "Krytyczny",
      warning: "Ostrzeżenie",
      info: "Info",
    };
    return labels[sev] ?? sev;
  }

  categoryLabel(cat: string): string {
    const labels: Record<string, string> = {
      syntax: "Składnia",
      logic: "Logika",
      semantic: "Semantyka",
      conformance: "Konformancja",
      dead_code: "Martwy kod",
    };
    return labels[cat] ?? cat;
  }

  /**
   * Licznik kategorii — snakeCaseInterceptor zamienia też klucze wewnętrzne
   * map (``dead_code`` → ``deadCode``), dlatego sprawdzamy obie postacie.
   */
  categoryCount(cat: string): number {
    const s = this.summary();
    if (!s?.byCategory) return 0;
    const camelKey = cat.replace(/_([a-z])/g, (_, c: string) =>
      c.toUpperCase(),
    );
    return s.byCategory[cat] ?? s.byCategory[camelKey] ?? 0;
  }

  /** Story 5.10 (AC4) — odrzuć jako fałszywy pozytyw i odśwież listę. */
  dismiss(error: CodeError): void {
    this.codeErrorsService
      .updateStatus(this.projectId(), error.id, "false_positive")
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => this.loadErrors(),
        error: () => this.loadErrors(),
      });
  }
}
