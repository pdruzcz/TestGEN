import { DatePipe, DecimalPipe } from "@angular/common";
import {
  Component,
  OnInit,
  computed,
  effect,
  inject,
  signal,
  viewChild,
} from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatIconModule } from "@angular/material/icon";
import { MatPaginator, MatPaginatorModule } from "@angular/material/paginator";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatSort, MatSortModule } from "@angular/material/sort";
import { MatTableDataSource, MatTableModule } from "@angular/material/table";
import { MatTooltipModule } from "@angular/material/tooltip";
import { RouterLink } from "@angular/router";
import { EMPTY, catchError, interval, switchMap } from "rxjs";
import { AuthService } from "../../core/services/auth.service";
import { FooterComponent } from "../../shared/components/footer.component";
import { NavbarComponent } from "../../shared/components/navbar.component";
import {
  AuditLogEntry,
  DashboardService,
  ProjectDashboardItem,
} from "./dashboard.service";

const STATUS_LABELS: Record<string, string> = {
  created: "Utworzony",
  active: "Aktywny",
  analyzing: "W analizie",
  completed: "Zakończony",
  archived: "Zarchiwizowany",
};

/**
 * Etykiety PL dla akcji z audit loga (dashboard — „Ostatnia aktywność").
 * Pełna lista emitowanych akcji: grep 'action="' w backend/app — trzymanie
 * mapingu 1:1 chroni przed surowymi kluczami (user.login_success itp.)
 * w interfejsie użytkownika.
 */
const ACTION_LABELS: Record<string, string> = {
  "project.created": "Utworzono projekt",
  "project.updated": "Zaktualizowano projekt",
  "project.deleted": "Usunięto projekt",
  "analysis.started": "Rozpoczęto analizę",
  "analysis.completed": "Zakończono analizę",
  "source_file.uploaded": "Wgrano pliki źródłowe",
  "source_file.extracted_from_archive": "Rozpakowano archiwum",
  "source_file.repo_connected": "Podłączono repozytorium",
  "uml_diagram.uploaded": "Wgrano diagram UML",
  "gui_screenshot.uploaded": "Wgrano zrzut ekranu GUI",
  "gui_dom_source.uploaded": "Wgrano źródło DOM GUI",
  "user.registered": "Zarejestrowano konto",
  "user.login": "Logowanie",
  "user.login_success": "Zalogowano",
  "user.login_failed": "Nieudane logowanie",
  "user.logout": "Wylogowano",
  "user.invited": "Zaproszono użytkownika",
  "user.invitation_accepted": "Przyjęto zaproszenie",
  "user.email_verified": "Potwierdzono e-mail",
  "user.password_changed": "Zmieniono hasło",
  "user.password_reset": "Zresetowano hasło",
  "user.password_reset_completed": "Ukończono reset hasła",
  "user.profile_updated": "Zaktualizowano profil",
  "user.role_changed": "Zmieniono rolę",
  "user.blocked": "Zablokowano użytkownika",
  "user.deactivated": "Dezaktywowano użytkownika",
  "tenant.plan_changed": "Zmieniono plan subskrypcji",
  "platform.config_updated": "Zaktualizowano konfigurację platformy",
  "admin.bootstrapped": "Zainicjalizowano administratora",
  anonymization_run: "Uruchomiono anonimizację",
  "test_case.update": "Zaktualizowano test",
  "test_case.status": "Zmieniono status testu",
  "test_case.bulk_update": "Masowa aktualizacja testów",
  "test_case.bulk_delete": "Usunięto testy",
};

@Component({
  selector: "app-dashboard",
  standalone: true,
  imports: [
    RouterLink,
    MatButtonModule,
    MatIconModule,
    MatCardModule,
    MatTableModule,
    MatSortModule,
    MatPaginatorModule,
    MatProgressBarModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    DatePipe,
    DecimalPipe,
    NavbarComponent,
    FooterComponent,
  ],
  template: `
    <div class="dashboard-page">
      <app-navbar activeLink="dashboard" />

      <main class="content" id="main-content" tabindex="-1">
        <!-- Welcome row -->
        <div class="welcome-row">
          <div class="welcome-text">
            <h1 class="welcome-title">Witaj, {{ userFirstName() }}</h1>
            <p class="welcome-sub">Oto przegląd Twojej aktywności w TestGEN.</p>
          </div>
          <div class="quick-actions">
            <!--
              AC6: szybkie akcje z prewybranym projektem. „Prewybrany" =
              ostatnio używany projekt (projects()[0], lista posortowana
              desc po created_at). Brak projektów → nawigacja na listę /projects,
              gdzie użytkownik może utworzyć nowy.
            -->
            <a
              mat-stroked-button
              [routerLink]="analysisLink()"
              [class.disabled-action]="projects().length === 0"
              class="quick-action-btn"
              aria-label="Nowa analiza"
            >
              <mat-icon>play_circle</mat-icon>
              Nowa analiza
            </a>
            <a
              mat-stroked-button
              [routerLink]="documentsLink()"
              [class.disabled-action]="projects().length === 0"
              class="quick-action-btn"
              aria-label="Upload dokumentacji"
            >
              <mat-icon>upload_file</mat-icon>
              Upload dokumentacji
            </a>
            <a
              mat-raised-button
              color="primary"
              routerLink="/projects"
              class="new-proj-btn"
            >
              <mat-icon>add</mat-icon>
              Nowy projekt
            </a>
          </div>
        </div>

        <!-- Loading bar -->
        @if (isLoadingSummary()) {
          <mat-progress-bar mode="indeterminate" aria-label="Ładowanie" />
        }

        <!-- Statistics cards -->
        <div class="stats-row">
          <mat-card class="stat-card">
            <mat-icon class="stat-icon">folder</mat-icon>
            <div class="stat-body">
              <span class="stat-label">Projekty</span>
              <span class="stat-value">{{
                statistics()?.totalProjects ?? 0
              }}</span>
            </div>
          </mat-card>

          <mat-card class="stat-card">
            <mat-icon class="stat-icon">analytics</mat-icon>
            <div class="stat-body">
              <span class="stat-label">Analizy w tym miesiącu</span>
              <span class="stat-value">{{
                statistics()?.analysesThisMonth ?? 0
              }}</span>
            </div>
          </mat-card>

          <mat-card class="stat-card">
            <mat-icon class="stat-icon">verified</mat-icon>
            <div class="stat-body">
              <span class="stat-label">Śr. zgodność</span>
              <span class="stat-value">
                {{
                  statistics()?.avgCompliance != null
                    ? (statistics()!.avgCompliance | number: "1.0-1") + "%"
                    : "—"
                }}
              </span>
            </div>
          </mat-card>

          <mat-card class="stat-card stat-dark">
            <mat-icon class="stat-icon">science</mat-icon>
            <div class="stat-body">
              <span class="stat-label">Test case'y</span>
              <span class="stat-value">{{
                statistics()?.totalTestCases ?? 0
              }}</span>
            </div>
          </mat-card>
        </div>

        <!-- Plan usage widget (owner/admin only) -->
        @if (planUsage(); as pu) {
          <mat-card class="plan-usage-card">
            <div class="plan-header">
              <mat-icon>workspace_premium</mat-icon>
              <div>
                <h2 class="plan-title">Plan {{ pu.plan }}</h2>
                <span class="plan-sub">
                  Wykorzystanie zasobów w bieżącym miesiącu
                </span>
              </div>
            </div>
            <div class="plan-body">
              <div class="plan-metric">
                <span class="plan-metric-label">Analizy</span>
                <span class="plan-metric-value">
                  @if (pu.analysesLimit === null) {
                    {{ pu.analysesUsed }} / bez limitu
                  } @else {
                    {{ pu.analysesUsed }} / {{ pu.analysesLimit }}
                  }
                </span>
                <mat-progress-bar
                  mode="determinate"
                  [value]="analysisUsagePercent()"
                  aria-label="Wykorzystanie limitu analiz"
                />
              </div>
              <div class="plan-metric">
                <span class="plan-metric-label">Projekty</span>
                <span class="plan-metric-value">{{ pu.projectsCount }}</span>
              </div>
            </div>
          </mat-card>
        }

        <!-- Bento grid -->
        <div class="bento-row">
          <!-- Projects table -->
          <mat-card class="card projects-card">
            <div class="card-header">
              <h2 class="card-title">Projekty</h2>
              <a class="card-link" routerLink="/projects">Zobacz wszystkie →</a>
            </div>

            @if (loadError()) {
              <p class="error-state" role="alert">
                <mat-icon>error_outline</mat-icon>
                {{ loadError() }}
                <button mat-button (click)="retrySummary()">
                  Spróbuj ponownie
                </button>
              </p>
            } @else if (projects().length === 0) {
              <p class="empty-state">
                Brak projektów. Utwórz pierwszy projekt, aby rozpocząć analizę.
              </p>
            } @else {
              <table
                mat-table
                [dataSource]="dataSource"
                matSort
                [matSortActive]="sortActive"
                matSortDirection="desc"
                [matSortDisableClear]="false"
                class="proj-table"
                aria-label="Lista projektów"
              >
                <ng-container matColumnDef="name">
                  <th
                    mat-header-cell
                    *matHeaderCellDef
                    mat-sort-header
                    scope="col"
                  >
                    Nazwa
                  </th>
                  <td mat-cell *matCellDef="let p">
                    <a class="proj-link" [routerLink]="['/projects', p.id]">
                      {{ p.name }}
                    </a>
                  </td>
                </ng-container>

                <ng-container matColumnDef="lastAnalysis">
                  <th
                    mat-header-cell
                    *matHeaderCellDef
                    mat-sort-header
                    scope="col"
                  >
                    Ostatnia analiza
                  </th>
                  <td mat-cell *matCellDef="let p">
                    {{
                      p.lastAnalysisAt
                        ? (p.lastAnalysisAt | date: "yyyy-MM-dd")
                        : "—"
                    }}
                  </td>
                </ng-container>

                <ng-container matColumnDef="compliance">
                  <th
                    mat-header-cell
                    *matHeaderCellDef
                    mat-sort-header
                    scope="col"
                  >
                    Zgodność
                  </th>
                  <td mat-cell *matCellDef="let p">
                    @if (p.complianceScore != null) {
                      <span
                        class="compliance-badge"
                        [class.compliance-high]="p.complianceScore >= 80"
                        [class.compliance-mid]="
                          p.complianceScore >= 50 && p.complianceScore < 80
                        "
                        [class.compliance-low]="p.complianceScore < 50"
                      >
                        {{ p.complianceScore | number: "1.0-0" }}%
                      </span>
                    } @else {
                      <span>—</span>
                    }
                  </td>
                </ng-container>

                <ng-container matColumnDef="testCases">
                  <th
                    mat-header-cell
                    *matHeaderCellDef
                    mat-sort-header
                    scope="col"
                  >
                    Testy
                  </th>
                  <td mat-cell *matCellDef="let p">
                    {{ p.testCasesCount }}
                  </td>
                </ng-container>

                <ng-container matColumnDef="status">
                  <th
                    mat-header-cell
                    *matHeaderCellDef
                    mat-sort-header
                    scope="col"
                  >
                    Status
                  </th>
                  <td mat-cell *matCellDef="let p">
                    <span class="proj-status" [class]="p.status">
                      {{ statusLabel(p.status) }}
                    </span>
                  </td>
                </ng-container>

                <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
                <tr
                  mat-row
                  *matRowDef="let row; columns: displayedColumns"
                  class="proj-row"
                ></tr>
              </table>

              <!--
                MatPaginator wymaga osobnego elementu. pageSize 10 — lista na
                dashboard to top projekty, nie pełna baza; użytkownik klika
                "Zobacz wszystkie" dla pełnej listy z większą paginacją.
              -->
              <mat-paginator
                [pageSize]="10"
                [pageSizeOptions]="[5, 10, 25]"
                [showFirstLastButtons]="true"
                aria-label="Paginacja projektów"
              />
            }
          </mat-card>

          <!-- Activity feed -->
          <mat-card class="card activity-card">
            <div class="card-header">
              <h2 class="card-title">Ostatnia aktywność</h2>
              @if (isLoadingActivity()) {
                <mat-spinner diameter="16" aria-label="Ładowanie" />
              }
            </div>

            @if (activity().length === 0) {
              <p class="empty-state">Brak aktywności do wyświetlenia.</p>
            } @else {
              <div class="activity-list">
                @for (item of activity(); track item.id) {
                  <div class="activity-item">
                    <div class="activity-dot"></div>
                    <div class="activity-info">
                      <span class="activity-text">{{
                        actionLabel(item.action)
                      }}</span>
                      <span class="activity-meta">
                        {{ item.userEmail ?? "System" }}
                        · {{ item.createdAt | date: "yyyy-MM-dd HH:mm" }}
                      </span>
                    </div>
                  </div>
                }
              </div>
            }

            <button
              mat-button
              color="warn"
              (click)="authService.logout()"
              class="logout-btn"
            >
              <mat-icon>logout</mat-icon>
              Wyloguj się
            </button>
          </mat-card>
        </div>
      </main>

      <app-footer />
    </div>
  `,
  styles: [
    `
      .dashboard-page {
        min-height: 100vh;
        background: #f7f8fa;
        display: flex;
        flex-direction: column;
      }

      .content {
        display: flex;
        flex-direction: column;
        gap: 24px;
        padding: 32px 48px 40px;
        flex: 1;
      }

      .welcome-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
        flex-wrap: wrap;
      }
      .welcome-text {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .quick-actions {
        display: flex;
        gap: 8px;
        align-items: center;
        flex-wrap: wrap;
      }
      .quick-action-btn {
        display: inline-flex !important;
        align-items: center;
        gap: 6px;
        text-decoration: none;
        border-radius: 10px;
      }
      /*
         Prewybrany projekt niedostępny (brak projektów) — nie blokujemy
         nawigacji (klik i tak prowadzi do /projects), ale sygnalizujemy
         wizualnie, że akcja wymaga najpierw utworzenia projektu.
      */
      .quick-action-btn.disabled-action {
        opacity: 0.5;
        pointer-events: none;
      }
      .welcome-title {
        font-size: 28px;
        font-weight: 700;
        color: #1a1a1a;
        margin: 0;
      }
      .welcome-sub {
        font-size: 15px;
        color: #4b5563;
        margin: 0;
      }
      .new-proj-btn {
        display: inline-flex !important;
        align-items: center;
        gap: 8px;
        padding: 10px 24px;
        border-radius: 12px;
        text-decoration: none;
      }

      .stats-row {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
      }
      .stat-card {
        border-radius: 16px;
        padding: 20px;
        display: flex;
        align-items: center;
        gap: 16px;
      }
      .stat-icon {
        font-size: 36px;
        width: 36px;
        height: 36px;
        color: #1976d2;
      }
      .stat-dark .stat-icon {
        color: #ffffff;
      }
      .stat-body {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .stat-label {
        font-size: 13px;
        /* WCAG 2.1 AA: #6b7280 na tle karty (#f4f3f6) daje 4.37:1 — za mało. */
        color: #4b5563;
      }
      .stat-dark .stat-label {
        color: #9ca3af;
      }
      .stat-value {
        font-size: 28px;
        font-weight: 700;
        color: #1a1a1a;
      }
      .stat-dark .stat-value {
        color: #ffffff;
      }
      .stat-dark {
        background: #1a1a1a;
      }

      .plan-usage-card {
        border-radius: 16px;
        padding: 20px;
      }
      .plan-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 16px;
      }
      .plan-header mat-icon {
        font-size: 32px;
        width: 32px;
        height: 32px;
        color: #1976d2;
      }
      .plan-title {
        font-size: 18px;
        font-weight: 600;
        margin: 0;
        text-transform: capitalize;
      }
      .plan-sub {
        font-size: 13px;
        color: #4b5563;
      }
      .plan-body {
        display: grid;
        grid-template-columns: 2fr 1fr;
        gap: 24px;
      }
      .plan-metric {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .plan-metric-label {
        font-size: 12px;
        color: #4b5563;
      }
      .plan-metric-value {
        font-size: 16px;
        font-weight: 600;
        color: #1a1a1a;
      }

      .bento-row {
        display: grid;
        grid-template-columns: 2fr 1fr;
        gap: 16px;
      }
      .card {
        border-radius: 16px;
        padding: 24px;
        display: flex;
        flex-direction: column;
        gap: 16px;
      }
      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      .card-title {
        font-size: 18px;
        font-weight: 600;
        color: #1a1a1a;
        margin: 0;
      }
      .card-link {
        font-size: 13px;
        color: #1565c0;
        text-decoration: none;
      }
      .card-link:hover {
        text-decoration: underline;
      }

      .proj-table {
        width: 100%;
      }
      .proj-link {
        color: #1a1a1a;
        text-decoration: none;
        font-weight: 500;
      }
      .proj-link:hover {
        color: #1976d2;
      }
      .proj-row:hover {
        background: #f9fafb;
      }
      .compliance-badge {
        font-size: 12px;
        padding: 2px 8px;
        border-radius: 9999px;
        font-weight: 500;
      }
      .compliance-high {
        background: #e8f5e9;
        color: #1b5e20;
      }
      .compliance-mid {
        background: #fff8e1;
        color: #e65100;
      }
      .compliance-low {
        background: #ffebee;
        color: #b71c1c;
      }
      .proj-status {
        font-size: 12px;
        padding: 2px 8px;
        border-radius: 9999px;
      }
      .proj-status.created {
        background: #e3f2fd;
        color: #1565c0;
      }
      .proj-status.active {
        background: #e8f5e9;
        color: #2e7d32;
      }
      .proj-status.analyzing {
        background: #fff8e1;
        color: #bf360c;
      }
      .proj-status.completed {
        background: #e8f5e9;
        color: #1b5e20;
      }
      .proj-status.archived {
        background: #f3f4f6;
        color: #4b5563;
      }

      .activity-list {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .activity-item {
        display: flex;
        gap: 12px;
        align-items: flex-start;
      }
      .activity-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #1976d2;
        margin-top: 6px;
        flex-shrink: 0;
      }
      .activity-info {
        display: flex;
        flex-direction: column;
        gap: 2px;
      }
      .activity-text {
        font-size: 14px;
        color: #1a1a1a;
      }
      .activity-meta {
        font-size: 12px;
        color: #4b5563;
      }
      .logout-btn {
        margin-top: auto;
        align-self: flex-start;
      }

      .empty-state {
        /* WCAG 2.1 AA: #6b7280 na tle karty (#f4f3f6) daje 4.37:1 — za mało. */
        color: #4b5563;
        font-style: italic;
        margin: 0;
      }

      .error-state {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
        color: #b3261e;
        margin: 0;
      }

      @media (max-width: 1024px) {
        .stats-row {
          grid-template-columns: repeat(2, 1fr);
        }
        .bento-row {
          grid-template-columns: 1fr;
        }
        .plan-body {
          grid-template-columns: 1fr;
        }
      }

      @media (max-width: 768px) {
        .content {
          padding: 16px;
        }
        .stats-row {
          grid-template-columns: 1fr;
        }
        .welcome-row {
          flex-direction: column;
          align-items: flex-start;
          gap: 12px;
        }
      }
    `,
  ],
})
export class DashboardComponent implements OnInit {
  readonly authService = inject(AuthService);
  private readonly dashboardService = inject(DashboardService);

  readonly projects = this.dashboardService.projectsSignal;
  readonly statistics = this.dashboardService.statisticsSignal;
  readonly planUsage = this.dashboardService.planUsageSignal;
  readonly activity = this.dashboardService.activitySignal;
  readonly isLoadingSummary = this.dashboardService.isLoadingSummarySignal;
  readonly isLoadingActivity = this.dashboardService.isLoadingActivitySignal;
  // Bez tego pusta lista projektów i awaria API wyglądały identycznie —
  // serwis ustawiał sygnał błędu, ale widok go nie renderował.
  readonly loadError = this.dashboardService.errorSignal;

  readonly displayedColumns = [
    "name",
    "lastAnalysis",
    "compliance",
    "testCases",
    "status",
  ];

  /**
   * MatTableDataSource wspiera sortowanie i paginację out-of-the-box —
   * ale wymaga podpięcia instancji MatSort i MatPaginator. Synchronizujemy
   * dane i zależności przez effect(), bo sygnał projects() jest źródłem
   * prawdy, a dataSource jest tylko adapterem do API Material Table.
   */
  readonly dataSource = new MatTableDataSource<ProjectDashboardItem>();
  readonly sort = viewChild(MatSort);
  readonly paginator = viewChild(MatPaginator);
  /** Domyślnie sortuj po ostatniej analizie — najbardziej użyteczne na top. */
  readonly sortActive = "lastAnalysis";

  /**
   * Mapowanie nazw kolumn (columnDef) na właściwości obiektu + null-last,
   * żeby brak compliance lub brak ostatniej analizy lądował na końcu listy
   * zamiast na początku (domyślne sortowanie JS sortuje null przed liczbami).
   */
  private static readonly SORT_ACCESSOR: Record<
    string,
    (p: ProjectDashboardItem) => string | number | null
  > = {
    name: (p) => p.name.toLowerCase(),
    lastAnalysis: (p) =>
      p.lastAnalysisAt ? new Date(p.lastAnalysisAt).getTime() : null,
    compliance: (p) => p.complianceScore,
    testCases: (p) => p.testCasesCount,
    status: (p) => p.status,
  };

  readonly userName = computed(
    () => this.authService.currentUserSignal()?.name ?? "",
  );
  readonly userFirstName = computed(() => this.userName().split(" ")[0]);

  readonly analysisUsagePercent = computed(() => {
    const pu = this.planUsage();
    if (!pu || !pu.analysesLimit) return 0; // null = unlimited (Premium)
    return Math.min(100, (pu.analysesUsed / pu.analysesLimit) * 100);
  });

  // Ostatnio używany projekt = pierwszy z listy (posortowana desc).
  readonly lastProject = computed(() => this.projects()[0] ?? null);

  /**
   * AC6: szybkie akcje z prewybranym projektem. Jeśli mamy co najmniej jeden
   * projekt, nawigujemy bezpośrednio do modułu; w przeciwnym razie na listę
   * /projects, gdzie użytkownik może utworzyć nowy.
   */
  readonly analysisLink = computed(() => {
    const p = this.lastProject();
    return p ? ["/projects", p.id, "analysis"] : ["/projects"];
  });

  readonly documentsLink = computed(() => {
    const p = this.lastProject();
    return p ? ["/projects", p.id, "documents"] : ["/projects"];
  });

  constructor() {
    // Mapuj columnDef na właściwość obiektu, z obsługą null-last dla
    // lastAnalysisAt i complianceScore — bez tego domyślny accessor zgubi
    // projekt z brakiem compliance gdzieś w środku sortowania.
    this.dataSource.sortingDataAccessor = (data, columnDef) => {
      const accessor = DashboardComponent.SORT_ACCESSOR[columnDef];
      if (!accessor) return "";
      const value = accessor(data);
      if (value == null) {
        // MatTableDataSource nie wspiera bezpośrednio null-last; używamy
        // wartości granicznych, które w naturalnym porządku liczbowym/czasowym
        // lądują na końcu niezależnie od kierunku sortowania. MatSort przełącza
        // kierunek, więc dla asc dajemy +Infinity, dla desc -Infinity.
        const dir = this.dataSource.sort?.direction ?? "asc";
        const isAsc = dir !== "desc";
        return isAsc ? Number.POSITIVE_INFINITY : Number.NEGATIVE_INFINITY;
      }
      return value;
    };

    // Poll activity feed every 30s — stops automatically when component destroyed.
    interval(30000)
      .pipe(
        // catchError wewnątrz switchMap, nie na zewnątrz — inaczej pierwszy
        // błąd (np. padnięty backend) kończyłby cały interwał na stałe.
        switchMap(() =>
          this.dashboardService.loadActivity().pipe(catchError(() => EMPTY)),
        ),
        takeUntilDestroyed(),
      )
      .subscribe();

    // Signal → MatTableDataSource.data
    effect(() => {
      this.dataSource.data = this.projects();
    });
    // Podpiecie sort/paginator gdy dostępne (viewChild resolves po render).
    effect(() => {
      const sort = this.sort();
      if (sort) {
        this.dataSource.sort = sort;
      }
    });
    effect(() => {
      const paginator = this.paginator();
      if (paginator) {
        this.dataSource.paginator = paginator;
      }
    });
  }

  ngOnInit(): void {
    this.loadSummary();
    this.dashboardService.loadActivity().subscribe({ error: () => undefined });
  }

  retrySummary(): void {
    this.loadSummary();
  }

  private loadSummary(): void {
    // Serwis raportuje błąd przez errorSignal, ale strumień i tak go emituje —
    // bez handlera vitest/przeglądarka zgłaszałyby nieobsłużony wyjątek.
    this.dashboardService.loadSummary().subscribe({ error: () => undefined });
  }

  statusLabel(status: string): string {
    return STATUS_LABELS[status] ?? status;
  }

  actionLabel(action: string): string {
    return ACTION_LABELS[action] ?? action;
  }
}
