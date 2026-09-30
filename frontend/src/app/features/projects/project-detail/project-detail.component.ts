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
import { NavbarComponent } from "../../../shared/components/navbar.component";
import { FooterComponent } from "../../../shared/components/footer.component";
import { LockedFeatureTabComponent } from "../../../shared/components/locked-feature-tab/locked-feature-tab.component";
import { ModuleLocksService } from "../../../core/services/module-locks.service";
import { ProjectService } from "../services/project.service";
import { Project } from "../models/project.model";

@Component({
  selector: "app-project-detail",
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatButtonModule,
    MatIconModule,
    NavbarComponent,
    FooterComponent,
    LockedFeatureTabComponent,
  ],
  template: `
    <div class="pd-page">
      <app-navbar activeLink="projects" />
      <main class="pd-content" id="main-content" tabindex="-1">
        <a mat-button routerLink="/projects" class="back-link">
          <mat-icon>arrow_back</mat-icon>
          Wróć do listy projektów
        </a>

        @if (isLoading()) {
          <div class="loading">Ladowanie...</div>
        } @else if (project()) {
          <div class="title-row">
            <h1 class="page-title">{{ project()!.name }}</h1>
            <span class="badge" [class]="'badge-' + project()!.status">
              {{ project()!.status }}
            </span>
          </div>

          @if (project()!.description) {
            <p class="desc">{{ project()!.description }}</p>
          }

          <!-- Przepływ pracy w trzech pasmach (makieta testgen.pen,
               2026-09): Dane → Akcje → Wyniki. Kolejność niesie informację;
               kolor nie — wszystkie przyciski stroked, kolor = stan. -->
          <div class="bands">
            <div class="actions" role="group" aria-label="Dane wejściowe">
              <a
                mat-stroked-button
                color="primary"
                [routerLink]="['/projects', projectId(), 'files']"
              >
                <mat-icon>upload_file</mat-icon>
                Wgraj pliki
              </a>
              <!-- Story 7.13: moduły gated — widoczne-zablokowane (kłódka +
                   tooltip z wymaganym planem; klik = CTA do /billing/plans). -->
              <a
                mat-stroked-button
                color="primary"
                [class.module-locked]="locks.isLocked('documentation')"
                [routerLink]="
                  locks.isLocked('documentation')
                    ? null
                    : ['/projects', projectId(), 'documents']
                "
              >
                <app-locked-feature-tab
                  [locked]="locks.isLocked('documentation')"
                  [requiredPlan]="locks.requiredPlanOf('documentation')"
                >
                  <mat-icon>description</mat-icon>
                  Dokumenty
                </app-locked-feature-tab>
              </a>
              <a
                mat-stroked-button
                color="primary"
                [class.module-locked]="locks.isLocked('uml')"
                [routerLink]="
                  locks.isLocked('uml')
                    ? null
                    : ['/projects', projectId(), 'uml']
                "
              >
                <app-locked-feature-tab
                  [locked]="locks.isLocked('uml')"
                  [requiredPlan]="locks.requiredPlanOf('uml')"
                >
                  <mat-icon>account_tree</mat-icon>
                  Diagramy UML
                </app-locked-feature-tab>
              </a>
              <a
                mat-stroked-button
                color="primary"
                [class.module-locked]="locks.isLocked('gui')"
                [routerLink]="
                  locks.isLocked('gui')
                    ? null
                    : ['/projects', projectId(), 'gui']
                "
              >
                <app-locked-feature-tab
                  [locked]="locks.isLocked('gui')"
                  [requiredPlan]="locks.requiredPlanOf('gui')"
                >
                  <mat-icon>image</mat-icon>
                  Zrzuty ekranu GUI
                </app-locked-feature-tab>
              </a>
              <a
                mat-stroked-button
                color="primary"
                [routerLink]="['/projects', projectId(), 'integrations']"
              >
                <mat-icon>extension</mat-icon>
                Integracje
              </a>
              <a
                mat-stroked-button
                color="primary"
                [routerLink]="['/projects', projectId(), 'ci-cd']"
              >
                <mat-icon>conveyor_belt</mat-icon>
                Konfiguracja CI/CD
              </a>
              <a
                mat-stroked-button
                color="primary"
                [routerLink]="['/projects', projectId(), 'import', 'jira']"
              >
                <mat-icon>download</mat-icon>
                Import z Jiry
              </a>
            </div>

            <div class="band-separator" role="separator"></div>

            <div
              class="actions"
              role="group"
              aria-label="Akcje — przetwarzanie"
            >
              <a
                mat-stroked-button
                color="primary"
                [routerLink]="['/projects', projectId(), 'preprocessing']"
              >
                <mat-icon>analytics</mat-icon>
                Preprocessing
              </a>
              <a
                mat-stroked-button
                color="primary"
                [routerLink]="['/projects', projectId(), 'analysis']"
              >
                <mat-icon>tune</mat-icon>
                Konfiguracja analizy
              </a>
              <a
                mat-stroked-button
                color="primary"
                [class.module-locked]="locks.isLocked('code_doc_consistency')"
                [routerLink]="
                  locks.isLocked('code_doc_consistency')
                    ? null
                    : ['/projects', projectId(), 'gap-analysis']
                "
              >
                <app-locked-feature-tab
                  [locked]="locks.isLocked('code_doc_consistency')"
                  [requiredPlan]="locks.requiredPlanOf('code_doc_consistency')"
                >
                  <mat-icon>find_in_page</mat-icon>
                  Luki funkcjonalne
                </app-locked-feature-tab>
              </a>
              <a
                mat-stroked-button
                color="primary"
                [class.module-locked]="locks.isLocked('functional_gaps')"
                [routerLink]="
                  locks.isLocked('functional_gaps')
                    ? null
                    : ['/projects', projectId(), 'code-errors']
                "
              >
                <app-locked-feature-tab
                  [locked]="locks.isLocked('functional_gaps')"
                  [requiredPlan]="locks.requiredPlanOf('functional_gaps')"
                >
                  <mat-icon>error_outline</mat-icon>
                  Błędy kodu
                </app-locked-feature-tab>
              </a>
              <a
                mat-stroked-button
                color="primary"
                [class.module-locked]="locks.isLocked('security')"
                [routerLink]="
                  locks.isLocked('security')
                    ? null
                    : ['/projects', projectId(), 'security']
                "
              >
                <app-locked-feature-tab
                  [locked]="locks.isLocked('security')"
                  [requiredPlan]="locks.requiredPlanOf('security')"
                >
                  <mat-icon>security</mat-icon>
                  Skanowanie bezpieczeństwa
                </app-locked-feature-tab>
              </a>
              <a
                mat-stroked-button
                color="primary"
                [class.module-locked]="locks.isLocked('gui')"
                [routerLink]="
                  locks.isLocked('gui')
                    ? null
                    : ['/projects', projectId(), 'healing']
                "
              >
                <app-locked-feature-tab
                  [locked]="locks.isLocked('gui')"
                  [requiredPlan]="locks.requiredPlanOf('gui')"
                >
                  <mat-icon>healing</mat-icon>
                  Self-healing
                </app-locked-feature-tab>
              </a>
              <a
                mat-stroked-button
                color="primary"
                [routerLink]="['/projects', projectId(), 'comparison']"
              >
                <mat-icon>compare_arrows</mat-icon>
                Porównanie wersji
              </a>
            </div>

            <div class="band-separator" role="separator"></div>

            <div class="actions" role="group" aria-label="Wyniki i efekty">
              <a
                mat-stroked-button
                color="primary"
                [class.module-locked]="locks.isLocked('documentation')"
                [routerLink]="
                  locks.isLocked('documentation')
                    ? null
                    : ['/projects', projectId(), 'requirements']
                "
              >
                <app-locked-feature-tab
                  [locked]="locks.isLocked('documentation')"
                  [requiredPlan]="locks.requiredPlanOf('documentation')"
                >
                  <mat-icon>checklist</mat-icon>
                  Wymagania
                </app-locked-feature-tab>
              </a>
              <a
                mat-stroked-button
                color="primary"
                [class.module-locked]="locks.isLocked('documentation')"
                [routerLink]="
                  locks.isLocked('documentation')
                    ? null
                    : ['/projects', projectId(), 'glossary']
                "
              >
                <app-locked-feature-tab
                  [locked]="locks.isLocked('documentation')"
                  [requiredPlan]="locks.requiredPlanOf('documentation')"
                >
                  <mat-icon>menu_book</mat-icon>
                  Glosariusz
                </app-locked-feature-tab>
              </a>
              <a
                mat-stroked-button
                color="primary"
                [class.module-locked]="locks.isLocked('documentation')"
                [routerLink]="
                  locks.isLocked('documentation')
                    ? null
                    : ['/projects', projectId(), 'inconsistencies']
                "
              >
                <app-locked-feature-tab
                  [locked]="locks.isLocked('documentation')"
                  [requiredPlan]="locks.requiredPlanOf('documentation')"
                >
                  <mat-icon>warning</mat-icon>
                  Niespójności
                </app-locked-feature-tab>
              </a>
              <a
                mat-stroked-button
                color="primary"
                [class.module-locked]="locks.isLocked('documentation')"
                [routerLink]="
                  locks.isLocked('documentation')
                    ? null
                    : ['/projects', projectId(), 'traceability']
                "
              >
                <app-locked-feature-tab
                  [locked]="locks.isLocked('documentation')"
                  [requiredPlan]="locks.requiredPlanOf('documentation')"
                >
                  <mat-icon>account_tree</mat-icon>
                  Traceability
                </app-locked-feature-tab>
              </a>
              <a
                mat-stroked-button
                color="primary"
                [class.module-locked]="locks.isLocked('documentation')"
                [routerLink]="
                  locks.isLocked('documentation')
                    ? null
                    : ['/projects', projectId(), 'coverage-report']
                "
              >
                <app-locked-feature-tab
                  [locked]="locks.isLocked('documentation')"
                  [requiredPlan]="locks.requiredPlanOf('documentation')"
                >
                  <mat-icon>compare_arrows</mat-icon>
                  Raport pokrycia
                </app-locked-feature-tab>
              </a>
              <a
                mat-stroked-button
                color="primary"
                [class.module-locked]="locks.isLocked('functional_gaps')"
                [routerLink]="
                  locks.isLocked('functional_gaps')
                    ? null
                    : ['/projects', projectId(), 'compliance']
                "
              >
                <app-locked-feature-tab
                  [locked]="locks.isLocked('functional_gaps')"
                  [requiredPlan]="locks.requiredPlanOf('functional_gaps')"
                >
                  <mat-icon>verified</mat-icon>
                  Compliance
                </app-locked-feature-tab>
              </a>
              <a
                mat-stroked-button
                color="primary"
                [class.module-locked]="locks.isLocked('functional_gaps')"
                [routerLink]="
                  locks.isLocked('functional_gaps')
                    ? null
                    : ['/projects', projectId(), 'recommendations']
                "
              >
                <app-locked-feature-tab
                  [locked]="locks.isLocked('functional_gaps')"
                  [requiredPlan]="locks.requiredPlanOf('functional_gaps')"
                >
                  <mat-icon>lightbulb</mat-icon>
                  Rekomendacje
                </app-locked-feature-tab>
              </a>
              <a
                mat-stroked-button
                color="primary"
                [routerLink]="['/projects', projectId(), 'results']"
              >
                <mat-icon>fact_check</mat-icon>
                Wyniki analizy
              </a>
              <a
                mat-stroked-button
                color="primary"
                [class.module-locked]="locks.isLocked('uml')"
                [routerLink]="
                  locks.isLocked('uml')
                    ? null
                    : ['/projects', projectId(), 'traceability-matrix']
                "
              >
                <app-locked-feature-tab
                  [locked]="locks.isLocked('uml')"
                  [requiredPlan]="locks.requiredPlanOf('uml')"
                >
                  <mat-icon>hub</mat-icon>
                  Macierz śledzenia
                </app-locked-feature-tab>
              </a>
              <a
                mat-stroked-button
                color="primary"
                [routerLink]="['/projects', projectId(), 'test-cases']"
              >
                <mat-icon>bug_report</mat-icon>
                Przypadki testowe
              </a>
              <a
                mat-stroked-button
                color="primary"
                [routerLink]="['/projects', projectId(), 'reports']"
              >
                <mat-icon>summarize</mat-icon>
                Raporty
              </a>
            </div>
          </div>
        }
      </main>
      <app-footer />
    </div>
  `,
  styles: [
    `
      .pd-page {
        min-height: 100vh;
        background: #f7f8fa;
        display: flex;
        flex-direction: column;
      }
      .pd-content {
        flex: 1;
        padding: 32px 48px;
        max-width: 1200px;
        width: 100%;
        margin: 0 auto;
        display: flex;
        flex-direction: column;
        gap: 24px;
      }
      .back-link {
        align-self: flex-start;
      }
      .loading {
        color: #6b7280;
        padding: 2rem;
      }
      .title-row {
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .page-title {
        font-size: 28px;
        font-weight: 700;
        color: #1a1a1a;
        margin: 0;
      }
      .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 8px;
        font-size: 12px;
        font-weight: 500;
        text-transform: uppercase;
      }
      .badge-created {
        background: #e3f2fd;
        color: #0d47a1;
      }
      .badge-active {
        background: #e8f5e9;
        color: #1b5e20;
      }
      .badge-analyzing {
        background: #fff8e1;
        color: #b26a00;
      }
      .badge-completed {
        background: #ede7f6;
        color: #4527a0;
      }
      .badge-archived {
        background: #eceff1;
        color: #455a64;
      }
      .desc {
        font-size: 15px;
        color: #4b5563;
        margin: 0;
      }
      .bands {
        display: flex;
        flex-direction: column;
        gap: 24px;
      }
      .actions {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
      }
      .band-separator {
        border-top: 1px solid #c9d2dc;
      }
      /* Ikony 18×18 jak na makiecie — domyślne 24px Materiala były
         zbyt duże obok stroked przycisków (2026-09). */
      .bands mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
      }
      /* Story 7.13 — moduł gated zablokowany: przygaszony (widoczne-zablokowane) */
      .module-locked {
        color: #78909c;
        border-color: #b0bec5;
      }

      /* Moduł zablokowany planem jest statyczny: hover/focus/active nie mogą
         zmieniać koloru (state-layer Materiala) ani puszczać ripple —
         informację o stanie dają kłódka + tooltip (Story 7.13, UX fix
         2026-09-29: guzik „ożywał" po najechaniu mimo blokady). */
      .module-locked:hover,
      .module-locked.cdk-focused,
      .module-locked:active {
        color: #78909c;
        border-color: #b0bec5;
      }

      .module-locked ::ng-deep .mat-mdc-button-persistent-ripple,
      .module-locked ::ng-deep .mat-mdc-button-ripple {
        display: none;
      }
    `,
  ],
})
export class ProjectDetailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly projectService = inject(ProjectService);

  /** Story 7.13 — blokady modułów gated (signals, reaktywny unlock). */
  readonly locks = inject(ModuleLocksService);

  readonly isLoading = signal(true);
  readonly project = signal<Project | null>(null);
  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  ngOnInit(): void {
    this.locks.ensureLoaded();
    this.projectService
      .get(this.projectId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (p) => {
          this.project.set(p);
          this.isLoading.set(false);
        },
        error: () => this.isLoading.set(false),
      });
  }
}
