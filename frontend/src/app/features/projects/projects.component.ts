import { DatePipe } from "@angular/common";
import {
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  signal,
} from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { FormControl, FormGroup, ReactiveFormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatDialog, MatDialogModule } from "@angular/material/dialog";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import {
  MatPaginatorIntl,
  MatPaginatorModule,
  PageEvent,
} from "@angular/material/paginator";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatSelectModule } from "@angular/material/select";
import { MatSnackBar, MatSnackBarModule } from "@angular/material/snack-bar";
import { MatTableModule } from "@angular/material/table";
import { MatTooltipModule } from "@angular/material/tooltip";
import { RouterLink } from "@angular/router";
import { debounceTime, distinctUntilChanged } from "rxjs";
import { AuthService } from "../../core/services/auth.service";
import { polishPaginatorIntl } from "../../shared/i18n/polish-paginator-intl";
import { NavbarComponent } from "../../shared/components/navbar.component";
import { FooterComponent } from "../../shared/components/footer.component";
import {
  Project,
  ProjectListQuery,
  ProjectStatus,
} from "./models/project.model";
import {
  ProjectDeleteDialogComponent,
  ProjectDeleteDialogData,
} from "./project-delete-dialog.component";
import {
  ProjectFormDialogComponent,
  ProjectFormDialogData,
} from "./project-form-dialog.component";
import { ProjectService } from "./services/project.service";

interface ProjectFiltersForm {
  status: FormControl<ProjectStatus | "">;
  language: FormControl<string>;
  sortBy: FormControl<NonNullable<ProjectListQuery["sortBy"]>>;
  sortOrder: FormControl<NonNullable<ProjectListQuery["sortOrder"]>>;
}

const STATUS_LABELS: Record<ProjectStatus, string> = {
  created: "Utworzony",
  active: "Aktywny",
  analyzing: "W analizie",
  completed: "Zakończony",
  archived: "Zarchiwizowany",
};

@Component({
  selector: "app-projects",
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    DatePipe,
    MatTableModule,
    MatPaginatorModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatDialogModule,
    MatSnackBarModule,
    MatTooltipModule,
    NavbarComponent,
    FooterComponent,
  ],
  providers: [{ provide: MatPaginatorIntl, useFactory: polishPaginatorIntl }],
  template: `
    <div class="projects-page">
      <app-navbar activeLink="projects" />

      <!-- Content -->
      <main class="content" id="main-content" tabindex="-1">
        <header class="projects-header">
          <div>
            <h1 class="page-title">Projekty</h1>
            <p class="page-subtitle">
              Zarządzaj projektami analizy kodu w ramach swojego zespołu.
            </p>
          </div>
          <button
            mat-raised-button
            color="primary"
            (click)="onCreate()"
            data-testid="project-create-button"
            class="create-btn"
          >
            <mat-icon>add</mat-icon>
            Nowy projekt
          </button>
        </header>

        <div class="filters-card">
          <form [formGroup]="filtersForm" class="filters-form">
            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>Status</mat-label>
              <mat-select formControlName="status" aria-label="Filtr statusu">
                <mat-option value="">Wszystkie</mat-option>
                @for (s of statuses; track s) {
                  <mat-option [value]="s">{{ statusLabel(s) }}</mat-option>
                }
              </mat-select>
            </mat-form-field>

            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>Język</mat-label>
              <input
                matInput
                formControlName="language"
                placeholder="np. python"
                aria-label="Filtr języka"
              />
            </mat-form-field>

            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>Sortuj wg</mat-label>
              <mat-select formControlName="sortBy" aria-label="Sortuj wg pola">
                <mat-option value="created_at">Data utworzenia</mat-option>
                <mat-option value="updated_at">Data modyfikacji</mat-option>
                <mat-option value="name">Nazwa</mat-option>
                <mat-option value="status">Status</mat-option>
              </mat-select>
            </mat-form-field>

            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>Kierunek</mat-label>
              <mat-select
                formControlName="sortOrder"
                aria-label="Kierunek sortowania"
              >
                <mat-option value="desc">Malejąco</mat-option>
                <mat-option value="asc">Rosnąco</mat-option>
              </mat-select>
            </mat-form-field>
          </form>
        </div>

        <div class="table-card">
          @if (errorMessage()) {
            <div class="error-banner" role="alert">
              <mat-icon>error</mat-icon>
              {{ errorMessage() }}
            </div>
          }

          @if (isLoading()) {
            <div class="loading-state" aria-live="polite">
              <mat-spinner diameter="40" aria-label="Ładowanie"></mat-spinner>
              <span>Ładowanie projektów…</span>
            </div>
          } @else if (projects().length === 0) {
            <div class="empty-state" role="status" aria-live="polite">
              <mat-icon>folder_off</mat-icon>
              <p>Brak projektów spełniających kryteria.</p>
              <button mat-stroked-button color="primary" (click)="onCreate()">
                <mat-icon>add</mat-icon>
                Utwórz pierwszy projekt
              </button>
            </div>
          } @else {
            <table
              mat-table
              [dataSource]="projects()"
              class="projects-table"
              aria-label="Lista projektów"
            >
              <caption class="visually-hidden">Lista projektów</caption>
              <ng-container matColumnDef="name">
                <th mat-header-cell *matHeaderCellDef scope="col">Nazwa</th>
                <td mat-cell *matCellDef="let p">
                  <div class="cell-name">
                    <a
                      class="cell-name-link"
                      [routerLink]="['/projects', p.id]"
                      >{{ p.name }}</a
                    >
                    @if (p.description) {
                      <span class="cell-description">{{ p.description }}</span>
                    }
                  </div>
                </td>
              </ng-container>

              <ng-container matColumnDef="status">
                <th mat-header-cell *matHeaderCellDef scope="col">Status</th>
                <td mat-cell *matCellDef="let p">
                  <span class="status-badge status-{{ p.status }}">
                    {{ statusLabel(p.status) }}
                  </span>
                </td>
              </ng-container>

              <ng-container matColumnDef="language">
                <th mat-header-cell *matHeaderCellDef scope="col">Język</th>
                <td mat-cell *matCellDef="let p">
                  {{ p.languageHint || "—" }}
                </td>
              </ng-container>

              <ng-container matColumnDef="createdAt">
                <th mat-header-cell *matHeaderCellDef scope="col">Utworzono</th>
                <td mat-cell *matCellDef="let p">
                  {{ p.createdAt | date: "yyyy-MM-dd HH:mm" }}
                </td>
              </ng-container>

              <ng-container matColumnDef="actions">
                <th
                  mat-header-cell
                  *matHeaderCellDef
                  scope="col"
                  class="col-actions"
                >
                  Akcje
                </th>
                <td mat-cell *matCellDef="let p" class="col-actions">
                  <a
                    mat-icon-button
                    [routerLink]="['/projects', p.id, 'files']"
                    matTooltip="Otwórz pliki projektu"
                    aria-label="Otwórz pliki projektu"
                    data-testid="project-open-button"
                  >
                    <mat-icon>folder_open</mat-icon>
                  </a>
                  @if (canManage()) {
                    <button
                      mat-icon-button
                      (click)="onEdit(p)"
                      matTooltip="Edytuj projekt"
                      aria-label="Edytuj projekt"
                      data-testid="project-edit-button"
                    >
                      <mat-icon>edit</mat-icon>
                    </button>
                    <button
                      mat-icon-button
                      color="warn"
                      (click)="onDelete(p)"
                      matTooltip="Usuń projekt"
                      aria-label="Usuń projekt"
                      data-testid="project-delete-button"
                    >
                      <mat-icon>delete</mat-icon>
                    </button>
                  }
                </td>
              </ng-container>

              <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
              <tr mat-row *matRowDef="let row; columns: displayedColumns"></tr>
            </table>

            <mat-paginator
              [length]="total()"
              [pageSize]="pageSize()"
              [pageIndex]="page() - 1"
              [pageSizeOptions]="[10, 20, 50, 100]"
              (page)="onPageChange($event)"
              aria-label="Paginacja listy projektów"
            ></mat-paginator>
          }
        </div>
      </main>

      <app-footer />
    </div>
  `,
  styles: [
    `
      .projects-page {
        min-height: 100vh;
        background: #f7f8fa;
        display: flex;
        flex-direction: column;
      }

      /* Content */
      .content {
        max-width: 1200px;
        width: 100%;
        margin: 0 auto;
        padding: 32px 48px 40px;
        display: flex;
        flex-direction: column;
        gap: 16px;
        flex: 1;
      }
      .projects-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        flex-wrap: wrap;
        gap: 1rem;
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
        margin: 4px 0 0;
      }
      .create-btn {
        display: inline-flex !important;
        align-items: center;
        gap: 8px;
        padding: 10px 24px;
        border-radius: 12px;
      }

      .filters-card {
        background: #ffffff;
        border-radius: 16px;
        padding: 16px 24px;
      }
      .filters-form {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 0.75rem 1rem;
      }
      .table-card {
        background: #ffffff;
        border-radius: 16px;
        padding: 0;
        overflow: hidden;
      }
      .error-banner {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 12px 16px;
        border-radius: 8px;
        margin: 16px;
        font-size: 14px;
        background: #fdecea;
        color: #611a15;
      }
      .loading-state,
      .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.75rem;
        padding: 3rem 1rem;
        color: #6b7280;
      }
      .empty-state mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        opacity: 0.4;
      }
      .projects-table {
        width: 100%;
      }
      .cell-name {
        display: flex;
        flex-direction: column;
      }
      .cell-name-link {
        font-weight: 700;
        color: #1a1a1a;
        text-decoration: none;
        cursor: pointer;
      }
      .cell-name-link:hover {
        color: #1976d2;
        text-decoration: underline;
      }
      .cell-description {
        color: #6b7280;
        font-size: 0.85rem;
        max-width: 420px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .status-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 999px;
        font-size: 13px;
        background: #e3f2fd;
        color: #0d47a1;
      }
      .status-created {
        background: #e3f2fd;
        color: #0d47a1;
      }
      .status-active {
        background: #e8f5e9;
        color: #1b5e20;
      }
      .status-analyzing {
        background: #fff8e1;
        color: #b26a00;
      }
      .status-completed {
        background: #ede7f6;
        color: #4527a0;
      }
      .status-archived {
        background: #eceff1;
        color: #455a64;
      }
      .col-actions {
        width: 160px;
        text-align: right;
      }

      @media (max-width: 768px) {
        .content {
          padding: 16px;
        }
      }
    `,
  ],
})
export class ProjectsComponent implements OnInit {
  private readonly destroyRef = inject(DestroyRef);
  private readonly projectService = inject(ProjectService);
  private readonly authService = inject(AuthService);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  readonly statuses: readonly ProjectStatus[] = [
    "created",
    "active",
    "analyzing",
    "completed",
    "archived",
  ];
  readonly displayedColumns = [
    "name",
    "status",
    "language",
    "createdAt",
    "actions",
  ];

  readonly projects = this.projectService.projectsSignal;
  readonly total = this.projectService.totalSignal;
  readonly isLoading = this.projectService.isLoadingSignal;
  readonly errorMessage = signal("");

  readonly page = signal(1);
  readonly pageSize = signal(20);

  readonly canManage = computed(() => {
    const role = this.authService.currentUserSignal()?.role;
    return role === "owner" || role === "admin";
  });

  readonly filtersForm = new FormGroup<ProjectFiltersForm>({
    status: new FormControl<ProjectStatus | "">("", { nonNullable: true }),
    language: new FormControl<string>("", { nonNullable: true }),
    sortBy: new FormControl<NonNullable<ProjectListQuery["sortBy"]>>(
      "created_at",
      { nonNullable: true },
    ),
    sortOrder: new FormControl<NonNullable<ProjectListQuery["sortOrder"]>>(
      "desc",
      { nonNullable: true },
    ),
  });

  ngOnInit(): void {
    // Debounce changes so typing into "language" does not spam the backend
    this.filtersForm.valueChanges
      .pipe(
        debounceTime(300),
        distinctUntilChanged((a, b) => JSON.stringify(a) === JSON.stringify(b)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(() => {
        this.page.set(1);
        this.loadProjects();
      });

    this.loadProjects();
  }

  statusLabel(status: ProjectStatus): string {
    return STATUS_LABELS[status];
  }

  onPageChange(event: PageEvent): void {
    this.page.set(event.pageIndex + 1);
    this.pageSize.set(event.pageSize);
    this.loadProjects();
  }

  onCreate(): void {
    const ref = this.dialog.open<
      ProjectFormDialogComponent,
      ProjectFormDialogData,
      Project | null
    >(ProjectFormDialogComponent, {
      data: { mode: "create" },
      autoFocus: true,
      restoreFocus: true,
    });

    ref
      .afterClosed()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((project) => {
        if (project) {
          this.snackBar.open("Projekt utworzony", "OK", { duration: 3000 });
          this.page.set(1);
          this.loadProjects();
        }
      });
  }

  onEdit(project: Project): void {
    const ref = this.dialog.open<
      ProjectFormDialogComponent,
      ProjectFormDialogData,
      Project | null
    >(ProjectFormDialogComponent, {
      data: { mode: "edit", project },
      autoFocus: true,
      restoreFocus: true,
    });

    ref
      .afterClosed()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((updated) => {
        if (updated) {
          this.snackBar.open("Projekt zaktualizowany", "OK", {
            duration: 3000,
          });
          this.loadProjects();
        }
      });
  }

  onDelete(project: Project): void {
    const ref = this.dialog.open<
      ProjectDeleteDialogComponent,
      ProjectDeleteDialogData,
      boolean
    >(ProjectDeleteDialogComponent, {
      data: { project },
      autoFocus: true,
      restoreFocus: true,
    });

    ref
      .afterClosed()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((confirmed) => {
        if (confirmed) {
          this.snackBar.open("Projekt usunięty", "OK", { duration: 3000 });
          const currentPage = this.page();
          // If we just deleted the last row on a page, step back
          if (this.projects().length === 1 && currentPage > 1) {
            this.page.set(currentPage - 1);
          }
          this.loadProjects();
        }
      });
  }

  private loadProjects(): void {
    const raw = this.filtersForm.getRawValue();
    const query: ProjectListQuery = {
      page: this.page(),
      pageSize: this.pageSize(),
      status: raw.status || null,
      language: raw.language?.trim() || null,
      sortBy: raw.sortBy,
      sortOrder: raw.sortOrder,
    };

    this.errorMessage.set("");
    this.projectService
      .list(query)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        error: () => {
          this.errorMessage.set(
            "Nie udało się załadować listy projektów. Spróbuj odświeżyć stronę.",
          );
        },
      });
  }
}
