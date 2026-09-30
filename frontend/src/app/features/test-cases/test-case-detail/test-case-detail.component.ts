import { Component, DestroyRef, OnInit, computed, inject, signal } from "@angular/core";
import { CommonModule } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { NavbarComponent } from "../../../shared/components/navbar.component";
import { FooterComponent } from "../../../shared/components/footer.component";
import { TestCaseService } from "../services/test-case.service";
import { TestCase, TestCaseExecution } from "../models/test-case.model";

@Component({
  selector: "app-test-case-detail",
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    NavbarComponent,
    FooterComponent,
  ],
  template: `
    <div class="detail-page">
      <app-navbar activeLink="projects" />

      <main class="detail-content" id="main-content" tabindex="-1">
        <a
          mat-button
          [routerLink]="['/projects', projectId(), 'test-cases']"
          class="back-link"
        >
          <mat-icon>arrow_back</mat-icon>
          Wroc do listy testow
        </a>

        @if (isLoading()) {
          <div class="loading">
            <mat-spinner diameter="24" aria-label="Ładowanie"></mat-spinner>
            <span>Ladowanie...</span>
          </div>
        } @else if (testCase()) {
          <div class="title-row">
            <h1 class="tc-title">{{ testCase()!.title }}</h1>
            <span class="badge" [class]="statusBadgeClass()">
              {{ testCase()!.status }}
            </span>
          </div>

          <div class="actions">
            <button mat-raised-button color="primary" (click)="runTest()">
              <mat-icon>play_arrow</mat-icon>
              Uruchom test
            </button>
            <button mat-stroked-button color="primary" (click)="reviewTest()">
              <mat-icon>check_circle</mat-icon>
              Zatwierdz
            </button>
          </div>

          <div class="card">
            <h2 class="card-title">Metadane</h2>
            <div class="meta-grid">
              <div class="meta-item">
                <span class="meta-label">Typ</span>
                <span class="meta-value">{{ testCase()!.type }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">Priorytet</span>
                <span class="meta-value">{{ testCase()!.priority }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">Framework</span>
                <span class="meta-value">{{ testCase()!.framework }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">Jezyk</span>
                <span class="meta-value">{{ testCase()!.language ?? '-' }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">Pewnosc</span>
                <span class="meta-value">
                  {{ testCase()!.confidenceScore ? (testCase()!.confidenceScore | number:'1.0-2') : '-' }}
                </span>
              </div>
              <div class="meta-item">
                <span class="meta-label">Plik zrodlowy</span>
                <span class="meta-value">{{ testCase()!.sourceFunction ?? '-' }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">Funkcja</span>
                <span class="meta-value">{{ testCase()!.sourceFunction ?? '-' }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">Utworzono</span>
                <span class="meta-value">{{ testCase()!.createdAt | date:'yyyy-MM-dd HH:mm' }}</span>
              </div>
            </div>
          </div>

          @if (testCase()!.testCode) {
            <div class="card">
              <h2 class="card-title">Kod testu</h2>
              <pre class="code-block"><code>{{ testCase()!.testCode }}</code></pre>
            </div>
          }

          <div class="card">
            <h2 class="card-title">Historia wykonan</h2>
            @if (executions().length === 0) {
              <p class="empty-text">Brak wykonan tego testu.</p>
            } @else {
              <table class="exec-table">
                <caption class="visually-hidden">Historia wykonań testu</caption>
                <thead>
                  <tr>
                    <th scope="col">Data</th>
                    <th scope="col">Status</th>
                    <th scope="col">Czas</th>
                    <th scope="col">Pokrycie</th>
                  </tr>
                </thead>
                <tbody>
                  @for (ex of executions(); track ex.id) {
                    <tr>
                      <td>{{ ex.executedAt | date:'yyyy-MM-dd HH:mm' }}</td>
                      <td>
                        <span class="badge" [class]="'badge-' + ex.status.toLowerCase()">
                          {{ ex.status }}
                        </span>
                      </td>
                      <td>{{ ex.executionDurationMs ? ex.executionDurationMs + ' ms' : '-' }}</td>
                      <td>
                        {{ ex.coveragePercentage ? (ex.coveragePercentage | number:'1.0-1') + '%' : '-' }}
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            }
          </div>
        }
      </main>

      <app-footer />
    </div>
  `,
  styles: [
    `
      .detail-page { min-height: 100vh; background: #f7f8fa; display: flex; flex-direction: column; }
      .detail-content { flex: 1; padding: 32px 48px; max-width: 960px; width: 100%; margin: 0 auto; display: flex; flex-direction: column; gap: 24px; }
      .back-link { align-self: flex-start; }
      .loading { display: flex; align-items: center; gap: 12px; padding: 3rem; justify-content: center; color: #6b7280; }
      .title-row { display: flex; align-items: center; gap: 12px; }
      .tc-title { font-size: 24px; font-weight: 600; color: #1a1a1a; margin: 0; }
      .badge { display: inline-block; padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 500; }
      .badge-draft { background: #f3f4f6; color: #6b7280; }
      .badge-ready { background: #e3f2fd; color: #0d47a1; }
      .badge-passed { background: #e8f5e9; color: #1b5e20; }
      .badge-failed { background: #fdecea; color: #611a15; }
      .badge-skipped { background: #fff8e1; color: #b26a00; }
      .badge-disabled { background: #eceff1; color: #455a64; }
      .actions { display: flex; gap: 8px; }
      .card { background: #ffffff; border-radius: 16px; padding: 24px; display: flex; flex-direction: column; gap: 16px; }
      .card-title { font-size: 18px; font-weight: 600; color: #1a1a1a; margin: 0; }
      .meta-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 24px; }
      .meta-item { display: flex; flex-direction: column; gap: 2px; }
      .meta-label { font-size: 12px; color: #6b7280; }
      .meta-value { font-size: 14px; font-weight: 500; color: #1a1a1a; }
      .code-block { background: #1e1e1e; border-radius: 12px; padding: 20px; overflow-x: auto; margin: 0; }
      .code-block code { font-family: 'Roboto Mono', monospace; font-size: 13px; color: #d4d4d4; white-space: pre; }
      .empty-text { color: #6b7280; font-style: italic; margin: 0; }
      .exec-table { width: 100%; border-collapse: collapse; }
      .exec-table th { text-align: left; padding: 8px 12px; font-size: 13px; font-weight: 500; color: #6b7280; background: #f7f8fa; }
      .exec-table td { padding: 8px 12px; border-top: 1px solid #e5e7eb; font-size: 14px; color: #4b5563; }
    `,
  ],
})
export class TestCaseDetailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly service = inject(TestCaseService);

  readonly isLoading = signal(true);
  readonly testCase = signal<TestCase | null>(null);
  readonly executions = signal<TestCaseExecution[]>([]);

  readonly projectId = computed(() => this.route.snapshot.paramMap.get("projectId") ?? "");
  readonly testCaseId = computed(() => this.route.snapshot.paramMap.get("testCaseId") ?? "");

  ngOnInit(): void {
    this.service.get(this.testCaseId()).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (tc) => { this.testCase.set(tc); this.isLoading.set(false); },
      error: () => this.isLoading.set(false),
    });
    this.service.listExecutions(this.testCaseId()).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (ex) => this.executions.set(ex),
    });
  }

  statusBadgeClass(): string {
    return `badge-${(this.testCase()?.status ?? "draft").toLowerCase()}`;
  }

  runTest(): void {
    this.service.execute(this.testCaseId()).pipe(takeUntilDestroyed(this.destroyRef)).subscribe();
  }

  reviewTest(): void {
    this.service.review(this.testCaseId()).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (tc) => this.testCase.set(tc),
    });
  }
}
