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
import {
  AbstractControl,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from "@angular/forms";
import { HttpErrorResponse } from "@angular/common/http";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatTabsModule } from "@angular/material/tabs";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatTableModule } from "@angular/material/table";
import { MatDividerModule } from "@angular/material/divider";
import {
  MatPaginatorIntl,
  MatPaginatorModule,
  PageEvent,
} from "@angular/material/paginator";
import { MatDialog, MatDialogModule } from "@angular/material/dialog";
import { MatTooltipModule } from "@angular/material/tooltip";
import { NavbarComponent } from "../../../shared/components/navbar.component";
import { FooterComponent } from "../../../shared/components/footer.component";
import { polishPaginatorIntl } from "../../../shared/i18n/polish-paginator-intl";
import { AuthService } from "../../../core/services/auth.service";
import {
  ProjectFilesService,
  SourceFile,
} from "../services/project-files.service";
import {
  SourceFileDeleteDialogComponent,
  SourceFileDeleteDialogData,
} from "./source-file-delete-dialog.component";

interface ConnectRepoForm {
  repoUrl: FormControl<string>;
  branch: FormControl<string>;
  authToken: FormControl<string>;
}

// Keep these in sync with backend/app/services/project/upload_service.py
const ALLOWED_EXTENSIONS: ReadonlyArray<string> = [
  ".py",
  ".java",
  ".js",
  ".ts",
  ".jsx",
  ".tsx",
  ".cs",
  ".cpp",
  ".c",
  ".h",
  ".hpp",
  ".go",
  ".rb",
  ".php",
  ".swift",
  ".kt",
  ".zip",
  ".tar.gz",
  ".tgz",
];

const ALLOWED_GIT_HOSTS = ["github.com", "gitlab.com", "bitbucket.org"];

// Client-side max-size sanity check — the Professional plan limit.
// The backend remains the authoritative source and will 429 anything
// exceeding the user's actual plan-based quota.
const MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024;

function extensionOf(filename: string): string {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".tar.gz")) return ".tar.gz";
  if (lower.endsWith(".tgz")) return ".tgz";
  const idx = lower.lastIndexOf(".");
  return idx === -1 ? "" : lower.slice(idx);
}

function isAllowedExtension(filename: string): boolean {
  return ALLOWED_EXTENSIONS.includes(extensionOf(filename));
}

function repoUrlValidator(control: AbstractControl): ValidationErrors | null {
  const raw = typeof control.value === "string" ? control.value : "";
  const value = raw.trim();
  if (!value) return null;
  if (!value.startsWith("https://")) {
    return { repoUrlScheme: true };
  }
  try {
    const url = new URL(value);
    if (!ALLOWED_GIT_HOSTS.includes(url.hostname)) {
      return { repoUrlHost: true };
    }
  } catch {
    return { repoUrlInvalid: true };
  }
  return null;
}

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(2)} GB`;
}

@Component({
  selector: "app-project-files",
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    RouterLink,
    MatTabsModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatFormFieldModule,
    MatInputModule,
    MatTableModule,
    MatDividerModule,
    MatPaginatorModule,
    MatDialogModule,
    MatTooltipModule,
    NavbarComponent,
    FooterComponent,
  ],
  providers: [{ provide: MatPaginatorIntl, useFactory: polishPaginatorIntl }],
  template: `
    <div class="files-page">
      <app-navbar activeLink="projects" />

      <!-- Content -->
      <main class="files-content" id="main-content" tabindex="-1">
        <div class="files-header">
          <a
            mat-button
            [routerLink]="['/projects', projectId()]"
            data-testid="back-to-project"
            class="back-link"
          >
            <mat-icon>arrow_back</mat-icon>
            Wróć do szczegółów projektu
          </a>
          <h1 class="page-title">Pliki projektu</h1>
          <p class="page-subtitle">
            Wgraj pliki kodu źródłowego lub podłącz repozytorium.
          </p>
        </div>

        <div class="tabs-card">
          <mat-tab-group aria-label="Źródła kodu projektu">
            <mat-tab label="Wgraj pliki">
              <div class="tab-content">
                <section
                  class="drop-zone"
                  [class.drag-active]="isDragActive()"
                  role="button"
                  tabindex="0"
                  aria-label="Strefa drag-and-drop. Naciśnij Enter aby wybrać pliki z dysku."
                  (dragover)="onDragOver($event)"
                  (dragleave)="onDragLeave($event)"
                  (drop)="onDrop($event)"
                  (click)="fileInput.click()"
                  (keydown.enter)="fileInput.click()"
                  (keydown.space)="fileInput.click(); $event.preventDefault()"
                >
                  <mat-icon aria-hidden="true">cloud_upload</mat-icon>
                  <p class="drop-main">
                    Przeciągnij pliki tutaj lub kliknij, aby wybrać
                  </p>
                  <p class="drop-hint">
                    Dozwolone rozszerzenia: {{ allowedExtensionsLabel }}
                  </p>
                  <input
                    #fileInput
                    hidden
                    type="file"
                    multiple
                    (change)="onFilesSelected($event)"
                  />
                </section>

                @if (uploadError()) {
                  <div class="error-banner" role="alert" aria-live="assertive">
                    <mat-icon aria-hidden="true">error</mat-icon>
                    {{ uploadError() }}
                  </div>
                }

                @if (uploadSummary()) {
                  <div class="success-banner" role="status" aria-live="polite">
                    <mat-icon aria-hidden="true">check_circle</mat-icon>
                    {{ uploadSummary() }}
                  </div>
                }

                @if (isUploading()) {
                  <div class="uploading" role="status" aria-live="polite">
                    <mat-spinner
                      diameter="24"
                      aria-label="Trwa przesyłanie plików"
                    ></mat-spinner>
                    <span>Trwa przesyłanie plików…</span>
                  </div>
                }

                @if (rejectedFiles().length > 0) {
                  <div class="rejected-list" role="status" aria-live="polite">
                    <h3>Pliki odrzucone</h3>
                    <ul>
                      @for (r of rejectedFiles(); track r.filename) {
                        <li>
                          <strong>{{ r.filename }}</strong> —
                          {{
                            r.rejectionReason ?? "Plik odrzucony przez serwer."
                          }}
                        </li>
                      }
                    </ul>
                  </div>
                }

                <mat-divider></mat-divider>

                <h3 class="section-title">
                  Pliki w projekcie
                  @if (total() > 0) {
                    <span class="total-count">({{ total() }})</span>
                  }
                </h3>

                @if (isLoadingList()) {
                  <div class="loading" role="status" aria-live="polite">
                    <mat-spinner
                      diameter="20"
                      aria-label="Ładowanie listy plików"
                    ></mat-spinner>
                    <span>Ładowanie listy plików…</span>
                  </div>
                } @else if (files().length === 0) {
                  <p class="empty">
                    Brak plików. Wgraj pierwsze źródła powyżej.
                  </p>
                } @else {
                  <table mat-table [dataSource]="files()" class="files-table">
                    <caption class="visually-hidden">Lista plików projektu</caption>
                    <ng-container matColumnDef="filename">
                      <th mat-header-cell *matHeaderCellDef scope="col">
                        Nazwa pliku
                      </th>
                      <td mat-cell *matCellDef="let f">{{ f.filename }}</td>
                    </ng-container>
                    <ng-container matColumnDef="size">
                      <th mat-header-cell *matHeaderCellDef scope="col">
                        Rozmiar
                      </th>
                      <td mat-cell *matCellDef="let f">
                        {{ formatSize(f.fileSize) }}
                      </td>
                    </ng-container>
                    <ng-container matColumnDef="hash">
                      <th mat-header-cell *matHeaderCellDef scope="col">
                        SHA-256
                      </th>
                      <td mat-cell *matCellDef="let f" class="hash">
                        <code [title]="f.sha256Hash"
                          >{{ f.sha256Hash?.slice(0, 12) }}…</code
                        >
                      </td>
                    </ng-container>
                    <ng-container matColumnDef="createdAt">
                      <th mat-header-cell *matHeaderCellDef scope="col">
                        Dodano
                      </th>
                      <td mat-cell *matCellDef="let f">
                        {{ f.createdAt | date: "yyyy-MM-dd HH:mm" }}
                      </td>
                    </ng-container>
                    <ng-container matColumnDef="actions">
                      <th mat-header-cell *matHeaderCellDef scope="col">
                        Akcje
                      </th>
                      <td mat-cell *matCellDef="let f">
                        <button
                          type="button"
                          mat-icon-button
                          color="warn"
                          matTooltip="Usuń plik"
                          aria-label="Usuń plik"
                          data-testid="delete-file"
                          [disabled]="isDeletingId() === f.id"
                          (click)="onDeleteFile(f, $event)"
                        >
                          @if (isDeletingId() === f.id) {
                            <mat-spinner
                              diameter="20"
                              aria-label="Usuwanie pliku"
                            ></mat-spinner>
                          } @else {
                            <mat-icon>delete</mat-icon>
                          }
                        </button>
                      </td>
                    </ng-container>

                    <tr
                      mat-header-row
                      *matHeaderRowDef="displayedColumns()"
                    ></tr>
                    <tr
                      mat-row
                      *matRowDef="let row; columns: displayedColumns()"
                    ></tr>
                  </table>

                  <mat-paginator
                    [length]="total()"
                    [pageSize]="pageSize()"
                    [pageIndex]="page() - 1"
                    [pageSizeOptions]="[20, 50, 100]"
                    (page)="onPageChange($event)"
                    aria-label="Paginacja listy plików"
                  ></mat-paginator>
                }
              </div>
            </mat-tab>

            <mat-tab label="Połącz repozytorium">
              <div class="tab-content">
                <form
                  [formGroup]="repoForm"
                  (ngSubmit)="onConnectRepo()"
                  class="repo-form"
                >
                  <mat-form-field
                    appearance="outline"
                    subscriptSizing="dynamic"
                    class="full-width"
                  >
                    <mat-label>Adres URL repozytorium (HTTPS)</mat-label>
                    <input
                      matInput
                      formControlName="repoUrl"
                      type="url"
                      autocomplete="url"
                      placeholder="https://github.com/organizacja/repo.git"
                      aria-describedby="repo-url-hint"
                    />
                    <mat-hint id="repo-url-hint"
                      >Obsługiwane: {{ allowedHostsLabel }}</mat-hint
                    >
                    @if (
                      repoForm.controls.repoUrl.hasError("required") &&
                      repoForm.controls.repoUrl.touched
                    ) {
                      <mat-error>Adres URL jest wymagany</mat-error>
                    }
                    @if (repoForm.controls.repoUrl.hasError("repoUrlScheme")) {
                      <mat-error
                        >Adres URL musi zaczynać się od https://</mat-error
                      >
                    }
                    @if (repoForm.controls.repoUrl.hasError("repoUrlHost")) {
                      <mat-error
                        >Nieobsługiwany dostawca. Dozwolone:
                        {{ allowedHostsLabel }}</mat-error
                      >
                    }
                    @if (repoForm.controls.repoUrl.hasError("repoUrlInvalid")) {
                      <mat-error>Podany URL jest nieprawidłowy</mat-error>
                    }
                  </mat-form-field>

                  <mat-form-field
                    appearance="outline"
                    subscriptSizing="dynamic"
                    class="full-width"
                  >
                    <mat-label>Gałąź</mat-label>
                    <input
                      matInput
                      formControlName="branch"
                      autocomplete="off"
                      aria-label="Nazwa gałęzi repozytorium"
                    />
                    @if (
                      repoForm.controls.branch.hasError("required") &&
                      repoForm.controls.branch.touched
                    ) {
                      <mat-error>Podaj nazwę gałęzi</mat-error>
                    }
                  </mat-form-field>

                  <mat-form-field
                    appearance="outline"
                    subscriptSizing="dynamic"
                    class="full-width"
                  >
                    <mat-label>Token dostępowy (opcjonalnie)</mat-label>
                    <input
                      matInput
                      formControlName="authToken"
                      type="password"
                      autocomplete="off"
                      aria-describedby="auth-token-hint"
                    />
                    <mat-hint id="auth-token-hint"
                      >Wymagany tylko dla repozytoriów prywatnych. Token nie
                      jest zapisywany po sklonowaniu.</mat-hint
                    >
                  </mat-form-field>

                  @if (repoError()) {
                    <div
                      class="error-banner"
                      role="alert"
                      aria-live="assertive"
                    >
                      <mat-icon aria-hidden="true">error</mat-icon>
                      {{ repoError() }}
                    </div>
                  }
                  @if (repoMessage()) {
                    <div
                      class="success-banner"
                      role="status"
                      aria-live="polite"
                    >
                      <mat-icon aria-hidden="true">check_circle</mat-icon>
                      {{ repoMessage() }}
                    </div>
                  }

                  <button
                    mat-raised-button
                    color="primary"
                    type="submit"
                    [disabled]="repoForm.invalid || isConnectingRepo()"
                    class="full-width"
                  >
                    @if (isConnectingRepo()) {
                      <mat-spinner
                        diameter="20"
                        aria-label="Łączenie z repozytorium"
                      ></mat-spinner>
                    } @else {
                      Połącz repozytorium
                    }
                  </button>
                </form>
              </div>
            </mat-tab>
          </mat-tab-group>
        </div>
      </main>

      <app-footer />
    </div>
  `,
  styles: [
    `
      .files-page {
        min-height: 100vh;
        background: #f7f8fa;
        display: flex;
        flex-direction: column;
      }

      /* Content */
      .files-content {
        flex: 1;
        padding: 32px 48px;
        max-width: 960px;
        width: 100%;
        margin: 0 auto;
      }
      .files-header {
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

      /* Tabs card */
      .tabs-card {
        background: #ffffff;
        border-radius: 16px;
        padding: 24px;
      }
      .tab-content {
        padding-top: 16px;
      }

      /* Drop zone */
      .drop-zone {
        border: 2px dashed #1976d2;
        border-radius: 16px;
        padding: 2rem;
        margin: 0.5rem 0 1rem;
        text-align: center;
        cursor: pointer;
        transition:
          background 0.2s ease,
          border-color 0.2s ease;
      }
      .drop-zone:focus-visible {
        outline: 3px solid #1976d2;
        outline-offset: 2px;
      }
      .drop-zone.drag-active {
        background: #e3f2fd;
        border-color: #1565c0;
      }
      .drop-zone mat-icon {
        font-size: 48px;
        height: 48px;
        width: 48px;
        color: #1976d2;
      }
      .drop-main {
        font-weight: 500;
        margin: 0.5rem 0 0.25rem;
        color: #1a1a1a;
      }
      .drop-hint {
        font-size: 0.85rem;
        color: #6b7280;
        margin: 0;
      }

      /* Banners */
      .error-banner,
      .success-banner {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 12px 16px;
        border-radius: 8px;
        margin: 1rem 0;
        font-size: 14px;
      }
      .error-banner {
        background: #fdecea;
        color: #611a15;
      }
      .success-banner {
        background: #e8f5e9;
        color: #1b5e20;
      }
      .uploading,
      .loading {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin: 1rem 0;
      }
      .rejected-list {
        background: #fff3e0;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
      }
      .rejected-list h3 {
        margin: 0 0 0.5rem;
        font-size: 1rem;
        color: #1a1a1a;
      }
      .rejected-list ul {
        margin: 0;
        padding-left: 1.5rem;
      }
      .section-title {
        margin: 1.5rem 0 0.75rem;
        font-size: 1.1rem;
        color: #1a1a1a;
      }
      .total-count {
        color: #6b7280;
        font-weight: normal;
        font-size: 0.9rem;
      }
      .empty {
        color: #6b7280;
        font-style: italic;
        margin: 1rem 0;
      }
      .files-table {
        width: 100%;
      }
      .hash code {
        font-size: 0.85rem;
      }
      .repo-form {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
      }
      .full-width {
        width: 100%;
      }
      @media (max-width: 768px) {
        .files-content {
          padding: 16px;
        }
        .top-nav {
          padding: 0 16px;
        }
        .nav-links {
          display: none;
        }
      }
    `,
  ],
})
export class ProjectFilesComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly service = inject(ProjectFilesService);
  private readonly authService = inject(AuthService);
  private readonly dialog = inject(MatDialog);

  readonly allowedExtensionsLabel = ALLOWED_EXTENSIONS.join(", ");
  readonly allowedHostsLabel = ALLOWED_GIT_HOSTS.join(", ");
  readonly formatSize = formatBytes;

  readonly files = signal<SourceFile[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly pageSize = signal(20);
  readonly isDeletingId = signal<string | null>(null);

  readonly canDelete = computed(() => {
    const role = this.authService.currentUserSignal()?.role;
    return role === "owner" || role === "admin";
  });

  readonly displayedColumns = computed<string[]>(() =>
    this.canDelete()
      ? ["filename", "size", "hash", "createdAt", "actions"]
      : ["filename", "size", "hash", "createdAt"],
  );
  readonly rejectedFiles = signal<
    { filename: string; rejectionReason: string | null }[]
  >([]);
  readonly isDragActive = signal(false);
  readonly isUploading = signal(false);
  readonly isLoadingList = signal(false);
  readonly isConnectingRepo = signal(false);
  readonly uploadError = signal("");
  readonly uploadSummary = signal("");
  readonly repoError = signal("");
  readonly repoMessage = signal("");

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  readonly repoForm = new FormGroup<ConnectRepoForm>({
    repoUrl: new FormControl("", {
      nonNullable: true,
      validators: [
        Validators.required,
        Validators.maxLength(2000),
        repoUrlValidator,
      ],
    }),
    branch: new FormControl("main", {
      nonNullable: true,
      validators: [Validators.required, Validators.maxLength(255)],
    }),
    authToken: new FormControl("", {
      nonNullable: true,
      validators: [Validators.maxLength(500)],
    }),
  });

  ngOnInit(): void {
    if (this.projectId()) {
      this.loadFiles();
    }
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.isDragActive.set(true);
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    this.isDragActive.set(false);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.isDragActive.set(false);
    const items = event.dataTransfer?.files;
    if (items && items.length > 0) {
      this.handleFiles(Array.from(items));
    }
  }

  onFilesSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.handleFiles(Array.from(input.files));
      input.value = "";
    }
  }

  private handleFiles(selected: File[]): void {
    this.uploadError.set("");
    this.uploadSummary.set("");

    const accepted: File[] = [];
    const rejected: { filename: string; rejectionReason: string | null }[] = [];

    for (const file of selected) {
      if (!isAllowedExtension(file.name)) {
        rejected.push({
          filename: file.name,
          rejectionReason: `Nieobsługiwane rozszerzenie. Dozwolone: ${ALLOWED_EXTENSIONS.join(", ")}`,
        });
        continue;
      }
      if (file.size > MAX_FILE_SIZE_BYTES) {
        rejected.push({
          filename: file.name,
          rejectionReason: `Plik przekracza limit ${formatBytes(MAX_FILE_SIZE_BYTES)}.`,
        });
        continue;
      }
      accepted.push(file);
    }

    this.rejectedFiles.set(rejected);

    if (accepted.length === 0) {
      if (rejected.length > 0) {
        this.uploadError.set(
          "Wszystkie wybrane pliki zostały odrzucone. Sprawdź listę powodów poniżej.",
        );
      }
      return;
    }

    this.uploadAccepted(accepted);
  }

  private uploadAccepted(files: File[]): void {
    const projectId = this.projectId();
    if (!projectId) return;

    this.isUploading.set(true);
    this.service
      .uploadFiles(projectId, files)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.isUploading.set(false);
          const serverRejected = (res.rejectedFiles ?? []).map((r) => ({
            filename: r.filename,
            rejectionReason: r.rejectionReason,
          }));
          if (serverRejected.length > 0) {
            this.rejectedFiles.update((prev) => [...prev, ...serverRejected]);
          }
          this.uploadSummary.set(
            `Zaakceptowano ${res.totalAccepted} z ${res.totalAccepted + res.totalRejected} plików.`,
          );
          this.loadFiles();
        },
        error: (err: HttpErrorResponse) => {
          this.isUploading.set(false);
          this.uploadError.set(this.extractErrorMessage(err));
        },
      });
  }

  private loadFiles(): void {
    const projectId = this.projectId();
    if (!projectId) return;

    this.isLoadingList.set(true);
    this.service
      .listFiles(projectId, this.page(), this.pageSize())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.files.set(res.files);
          this.total.set(res.total);
          this.isLoadingList.set(false);
        },
        error: () => {
          this.isLoadingList.set(false);
          this.uploadError.set("Nie udało się załadować listy plików.");
        },
      });
  }

  onPageChange(event: PageEvent): void {
    this.page.set(event.pageIndex + 1);
    this.pageSize.set(event.pageSize);
    this.loadFiles();
  }

  onDeleteFile(file: SourceFile, event: Event): void {
    event.stopPropagation();
    const projectId = this.projectId();
    if (!projectId) return;
    if (this.isDeletingId() === file.id) return;

    this.isDeletingId.set(file.id);
    const dialogData: SourceFileDeleteDialogData = {
      fileId: file.id,
      filename: file.filename,
      projectId,
    };
    this.dialog
      .open(SourceFileDeleteDialogComponent, { data: dialogData })
      .afterClosed()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((deleted: boolean | undefined) => {
        this.isDeletingId.set(null);
        if (!deleted) return;
        // If the only row on a non-first page was removed, step back so the
        // user doesn't land on an empty page.
        if (this.files().length === 1 && this.page() > 1) {
          this.page.set(this.page() - 1);
        }
        this.loadFiles();
      });
  }

  onConnectRepo(): void {
    if (this.repoForm.invalid || this.isConnectingRepo()) return;
    const projectId = this.projectId();
    if (!projectId) return;

    this.repoError.set("");
    this.repoMessage.set("");
    this.isConnectingRepo.set(true);

    const { repoUrl, branch, authToken } = this.repoForm.getRawValue();
    this.service
      .connectRepo(projectId, {
        repoUrl: repoUrl.trim(),
        branch: branch.trim(),
        authToken: authToken ? authToken.trim() : null,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.isConnectingRepo.set(false);
          this.repoMessage.set(
            `Repozytorium podłączone. Zindeksowano ${res.filesIndexed} plików.`,
          );
          this.repoForm.patchValue({ authToken: "" });
          this.loadFiles();
        },
        error: (err: HttpErrorResponse) => {
          this.isConnectingRepo.set(false);
          this.repoError.set(this.extractErrorMessage(err));
        },
      });
  }

  private extractErrorMessage(err: HttpErrorResponse): string {
    if (err.status === 401)
      return "Sesja wygasła. Zaloguj się ponownie, aby kontynuować.";
    if (err.status === 403)
      return "Brak uprawnień do tej operacji w tym projekcie.";
    if (err.status === 404) return "Nie znaleziono projektu o podanym ID.";
    if (err.status === 429)
      return "Przekroczony limit. Sprawdź plan lub zmniejsz rozmiar pliku.";
    return "Wystąpił błąd. Spróbuj ponownie.";
  }
}
