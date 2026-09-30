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
import { MatChipsModule } from "@angular/material/chips";
import { MatSelectModule } from "@angular/material/select";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatSnackBar, MatSnackBarModule } from "@angular/material/snack-bar";
import { NavbarComponent } from "../../../shared/components/navbar.component";
import { FooterComponent } from "../../../shared/components/footer.component";
import {
  PreprocessingService,
  LanguageStat,
} from "../services/preprocessing.service";

const LANGUAGE_LABELS: Record<string, string> = {
  python: "Python",
  java: "Java",
  javascript: "JavaScript",
  typescript: "TypeScript",
  csharp: "C#",
  cpp: "C/C++",
  go: "Go",
  ruby: "Ruby",
  php: "PHP",
  swift: "Swift",
  kotlin: "Kotlin",
  unknown: "Nieznany",
};

const LANGUAGE_OPTIONS = [
  "python",
  "java",
  "javascript",
  "typescript",
  "csharp",
  "cpp",
  "go",
  "ruby",
  "php",
  "swift",
  "kotlin",
];

@Component({
  selector: "app-preprocessing-report",
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatChipsModule,
    MatSelectModule,
    MatFormFieldModule,
    MatSnackBarModule,
    NavbarComponent,
    FooterComponent,
  ],
  template: `
    <div class="report-page">
      <app-navbar activeLink="projects" />

      <main class="report-content" id="main-content" tabindex="-1">
        <div class="report-header">
          <a
            mat-button
            [routerLink]="['/projects', projectId()]"
            data-testid="back-to-project"
            class="back-link"
          >
            <mat-icon>arrow_back</mat-icon>
            Wróć do szczegółów projektu
          </a>
          <h1 class="page-title">Raport preprocessingu</h1>
          <p class="page-subtitle">
            Automatycznie wykryte języki programowania i frameworki testowe.
          </p>
        </div>

        @if (isLoading()) {
          <div class="loading" role="status" aria-live="polite">
            <mat-spinner
              diameter="32"
              aria-label="Trwa analiza plików"
            ></mat-spinner>
            <span>Trwa analiza plików…</span>
          </div>
        } @else if (error()) {
          <div class="error-banner" role="alert" aria-live="assertive">
            <mat-icon aria-hidden="true">error</mat-icon>
            {{ error() }}
          </div>
          <button
            mat-raised-button
            color="primary"
            (click)="runPreprocessing()"
          >
            Uruchom preprocessing
          </button>
        } @else if (report()) {
          <div class="report-card">
            <!-- Languages section -->
            <section aria-label="Wykryte języki">
              <h2 class="section-title">
                <mat-icon aria-hidden="true">code</mat-icon>
                Wykryte języki
              </h2>
              <div class="chips-row">
                @for (lang of report()!.languages; track lang.language) {
                  <mat-chip
                    [highlighted]="true"
                    [aria-label]="
                      languageLabel(lang.language) +
                      ', ' +
                      lang.count +
                      ' plików'
                    "
                  >
                    {{ languageLabel(lang.language) }}
                    <span class="chip-count">{{ lang.count }} plików</span>
                    <span class="chip-loc">{{ formatLoc(lang.loc) }} LOC</span>
                  </mat-chip>
                }
              </div>
            </section>

            <!-- Frameworks section -->
            @if (report()!.detectedFrameworks.length > 0) {
              <section aria-label="Frameworki testowe" class="mt-24">
                <h2 class="section-title">
                  <mat-icon aria-hidden="true">science</mat-icon>
                  Frameworki testowe
                </h2>
                <div class="chips-row">
                  @for (fw of report()!.detectedFrameworks; track fw) {
                    <mat-chip>{{ fw }}</mat-chip>
                  }
                </div>
              </section>
            }

            <!-- Summary -->
            <section aria-label="Podsumowanie" class="mt-24 summary">
              <div class="summary-item">
                <span class="summary-label">Łączne LOC:</span>
                <span class="summary-value">{{
                  formatLoc(report()!.totalLoc)
                }}</span>
              </div>
            </section>

            <!-- Unknown files -->
            @if (report()!.unknownFiles.length > 0) {
              <section aria-label="Pliki wymagające klasyfikacji" class="mt-24">
                <h2 class="section-title warning-title">
                  <mat-icon aria-hidden="true">warning</mat-icon>
                  Pliki wymagające klasyfikacji
                </h2>
                <p class="hint">
                  Kliknij język obok pliku, aby go ręcznie sklasyfikować.
                </p>
                <ul class="unknown-list">
                  @for (file of unknownFiles(); track file.filename) {
                    <li class="unknown-item">
                      <span class="filename">{{ file.filename }}</span>
                      <mat-form-field
                        appearance="outline"
                        subscriptSizing="dynamic"
                        class="lang-select"
                      >
                        <mat-label>Wybierz język</mat-label>
                        <mat-select
                          [aria-label]="'Klasyfikuj ' + file.filename"
                          (selectionChange)="
                            onClassifyFile(file.fileId, $event.value)
                          "
                        >
                          @for (lang of languageOptions; track lang) {
                            <mat-option [value]="lang">{{
                              languageLabel(lang)
                            }}</mat-option>
                          }
                        </mat-select>
                      </mat-form-field>
                    </li>
                  }
                </ul>
              </section>
            }

            <!-- Re-run button -->
            <div class="actions mt-24">
              <button
                mat-stroked-button
                color="primary"
                (click)="runPreprocessing()"
              >
                <mat-icon>refresh</mat-icon>
                Uruchom ponownie
              </button>
            </div>
          </div>
        } @else {
          <div class="empty-state">
            <mat-icon aria-hidden="true">search</mat-icon>
            <p>Brak raportu preprocessingu dla tego projektu.</p>
            <button
              mat-raised-button
              color="primary"
              (click)="runPreprocessing()"
            >
              Uruchom preprocessing
            </button>
          </div>
        }
      </main>

      <app-footer />
    </div>
  `,
  styles: [
    `
      .report-page {
        min-height: 100vh;
        background: #f7f8fa;
        display: flex;
        flex-direction: column;
      }
      .report-content {
        flex: 1;
        padding: 32px 48px;
        max-width: 960px;
        width: 100%;
        margin: 0 auto;
      }
      .report-header {
        display: flex;
        flex-direction: column;
        gap: 4px;
        margin-bottom: 24px;
      }
      .back-link {
        align-self: flex-start;
        margin-bottom: 8px;
      }
      .page-title {
        font-size: 28px;
        font-weight: 700;
        color: #1a1a1a;
        margin: 0;
      }
      .page-subtitle {
        font-size: 15px;
        color: #4b5563;
        margin: 0;
      }
      .loading {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 3rem 0;
        justify-content: center;
      }
      .error-banner {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 12px 16px;
        border-radius: 8px;
        margin: 1rem 0;
        background: #fdecea;
        color: #611a15;
      }
      .report-card {
        background: #ffffff;
        border-radius: 16px;
        padding: 24px;
      }
      .section-title {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 1.1rem;
        font-weight: 600;
        color: #1a1a1a;
        margin: 0 0 12px;
      }
      .warning-title {
        color: #e65100;
      }
      .chips-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
      .chip-count {
        font-size: 0.8rem;
        opacity: 0.7;
        margin-left: 4px;
      }
      .chip-loc {
        font-size: 0.75rem;
        opacity: 0.5;
        margin-left: 4px;
      }
      .summary {
        display: flex;
        gap: 2rem;
        padding: 16px 0;
        border-top: 1px solid #e5e7eb;
      }
      .summary-item {
        display: flex;
        flex-direction: column;
      }
      .summary-label {
        font-size: 0.85rem;
        color: #6b7280;
      }
      .summary-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1a1a1a;
      }
      .hint {
        font-size: 0.85rem;
        color: #6b7280;
        margin: 0 0 12px;
      }
      .unknown-list {
        list-style: none;
        padding: 0;
        margin: 0;
      }
      .unknown-item {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 8px 0;
        border-bottom: 1px solid #f3f4f6;
      }
      .filename {
        flex: 1;
        font-weight: 500;
        color: #1a1a1a;
      }
      .lang-select {
        width: 180px;
      }
      .actions {
        padding-top: 16px;
        border-top: 1px solid #e5e7eb;
      }
      .empty-state {
        text-align: center;
        padding: 3rem 0;
      }
      .empty-state mat-icon {
        font-size: 48px;
        height: 48px;
        width: 48px;
        color: #9ca3af;
      }
      .empty-state p {
        color: #6b7280;
        margin: 1rem 0;
      }
      .mt-24 {
        margin-top: 24px;
      }
      @media (max-width: 768px) {
        .report-content {
          padding: 16px;
        }
      }
    `,
  ],
})
export class PreprocessingReportComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly service = inject(PreprocessingService);
  private readonly snackBar = inject(MatSnackBar);

  readonly languageOptions = LANGUAGE_OPTIONS;
  readonly report = this.service.reportSignal;
  readonly isLoading = this.service.isLoadingSignal;
  readonly error = this.service.errorSignal;

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  readonly unknownFiles = computed(() => {
    const r = this.report();
    if (!r) return [];
    return r.unknownFiles;
  });

  ngOnInit(): void {
    this.destroyRef.onDestroy(() => this.service.cancelPolling());
    const pid = this.projectId();
    if (pid) {
      this.service.loadReport(pid);
    }
  }

  runPreprocessing(): void {
    const pid = this.projectId();
    if (pid) {
      this.service.triggerPreprocessing(pid);
    }
  }

  onClassifyFile(fileId: string, language: string): void {
    const pid = this.projectId();
    if (!pid || !fileId) return;

    this.service
      .classifyFile(pid, fileId, { detectedLanguage: language })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.snackBar.open("Język zaktualizowany.", "OK", { duration: 3000 });
          this.service.loadReport(pid);
        },
        error: () => {
          this.snackBar.open("Nie udało się zaktualizować języka.", "OK", {
            duration: 3000,
          });
        },
      });
  }

  languageLabel(lang: string): string {
    return LANGUAGE_LABELS[lang] ?? lang;
  }

  formatLoc(loc: number): string {
    return loc.toLocaleString("pl-PL");
  }
}
