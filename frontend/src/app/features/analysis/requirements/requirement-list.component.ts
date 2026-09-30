import { Component, inject, signal, computed, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { DestroyRef } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatSelectModule } from "@angular/material/select";
import { MatChipsModule } from "@angular/material/chips";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { NavbarComponent } from "../../../shared/components/navbar.component";
import { FooterComponent } from "../../../shared/components/footer.component";
import {
  DocumentAnalysisService,
  Requirement as ApiRequirement,
} from "../../../services/document-analysis.service";

interface Requirement {
  req_id: string;
  /** Widok projektowy: dokument źródłowy wymogu (akcje per wiersz). */
  document_id?: string;
  document_filename?: string | null;
  text: string;
  type: "functional" | "non-functional";
  priority: "critical" | "high" | "medium" | "low" | null;
  source_section_id: string;
  source_section_title: string;
  confidence: number;
  extraction_method: "native" | "llm" | "hybrid_merged";
  /** Optional LLM justification (Story 2.5) — shown when present. */
  reasoning: string | null;
  status: string;
  accepted?: boolean;
  rejected?: boolean;
}

@Component({
  selector: "app-requirement-list",
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatIconModule,
    MatInputModule,
    MatFormFieldModule,
    MatSelectModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    RouterLink,
    NavbarComponent,
    FooterComponent,
  ],
  template: `
    <div class="view-page">
      <app-navbar activeLink="projects" />

      <main class="view-content" id="main-content" tabindex="-1">
        <!-- Header -->
        <div class="page-header">
          <a
            mat-button
            [routerLink]="['/projects', projectId(), 'documents']"
            class="back-link"
          >
            <mat-icon>arrow_back</mat-icon>
            Wróć do dokumentów
          </a>

          @if (documentTitle()) {
            <div class="header-info">
              <h1 class="page-title">Wymagania z: {{ documentTitle() }}</h1>
              <div class="badge">
                Znaleziono: {{ filteredRequirements().length }}
                {{ totalRequirements() > 0 ? "z " + totalRequirements() : "" }}
              </div>
            </div>
          }

          @if (isLoading()) {
            <div class="loading" role="status" aria-live="polite">
              <mat-spinner diameter="24" aria-label="Ładowanie"></mat-spinner>
              <span>Ładowanie wymagań…</span>
            </div>
          }
        </div>

        <!-- Filters -->
        @if (!isLoading() && requirements().length > 0) {
          <div class="filters">
            <mat-form-field appearance="outline" class="filter-field">
              <mat-icon matPrefix>filter_list</mat-icon>
              <mat-label>Typ</mat-label>
              <mat-select
                [(value)]="selectedType"
                (selectionChange)="onFilterChange()"
              >
                <mat-option value="all">Wszystkie</mat-option>
                <mat-option value="functional">Funkcjonalne</mat-option>
                <mat-option value="non-functional">Niefunkcjonalne</mat-option>
              </mat-select>
            </mat-form-field>

            <mat-form-field appearance="outline" class="filter-field">
              <mat-icon matPrefix>sort</mat-icon>
              <mat-label>Priorytet</mat-label>
              <mat-select
                [(value)]="selectedPriority"
                (selectionChange)="onFilterChange()"
              >
                <mat-option value="all">Wszystkie</mat-option>
                <mat-option value="critical">Krytyczne</mat-option>
                <mat-option value="high">Wysokie</mat-option>
                <mat-option value="medium">Średnie</mat-option>
                <mat-option value="low">Niskie</mat-option>
              </mat-select>
            </mat-form-field>

            <mat-form-field appearance="outline" class="search-field">
              <mat-icon matPrefix>search</mat-icon>
              <input
                matInput
                placeholder="Szukaj wymagań…"
                [value]="searchQuery()"
                (input)="searchQuery.set($any($event.target).value)"
              />
            </mat-form-field>

            <div class="stats">
              <span class="stat">
                <mat-icon aria-hidden="true">check_circle</mat-icon>
                Zaakceptowane: {{ acceptedCount() }}
              </span>
              <span class="stat">
                <mat-icon aria-hidden="true">cancel</mat-icon>
                Odrzucone: {{ rejectedCount() }}
              </span>
              <span class="stat">
                <mat-icon aria-hidden="true">pending</mat-icon>
                Oczekujące: {{ pendingCount() }}
              </span>
            </div>
          </div>
        }

        <!-- Requirements List -->
        @if (!isLoading()) {
          @if (filteredRequirements().length > 0) {
            <div class="requirements-list">
              @for (req of filteredRequirements(); track req.req_id) {
                <div
                  class="requirement-card"
                  [class.accepted]="req.accepted"
                  [class.rejected]="req.rejected"
                >
                  <div class="req-header">
                    <div class="req-id-type">
                      <span class="req-id">{{ req.req_id }}</span>
                      @if (isProjectView() && req.document_filename) {
                        <span class="doc-badge" title="Dokument źródłowy">{{
                          req.document_filename
                        }}</span>
                      }
                      <mat-chip
                        class="type-chip"
                        [color]="
                          req.type === 'functional' ? 'primary' : 'accent'
                        "
                      >
                        {{
                          req.type === "functional"
                            ? "Funkcjonalne"
                            : "Niefunkcjonalne"
                        }}
                      </mat-chip>
                      @if (req.priority) {
                        <mat-chip [class]="'priority-' + req.priority">
                          {{ getPriorityLabel(req.priority) }}
                        </mat-chip>
                      }
                    </div>
                    <div class="req-confidence">
                      <mat-icon aria-hidden="true" class="confidence-icon">
                        {{ getConfidenceIcon(req.confidence) }}
                      </mat-icon>
                      {{ req.confidence.toFixed(0) }}%
                      <span class="method">{{ req.extraction_method }}</span>
                    </div>
                  </div>

                  <div class="req-content">
                    <p class="req-text">{{ req.text }}</p>
                  </div>

                  @if (req.reasoning) {
                    <div class="req-reasoning">
                      <mat-icon aria-hidden="true">lightbulb</mat-icon>
                      <div class="reasoning-body">
                        <span class="reasoning-label">Uzasadnienie LLM</span>
                        <p class="reasoning-text">{{ req.reasoning }}</p>
                      </div>
                    </div>
                  }

                  <div class="req-source">
                    <mat-icon aria-hidden="true">location_on</mat-icon>
                    <span>{{ req.source_section_title }}</span>
                    <a
                      mat-button
                      class="view-link"
                      [routerLink]="[
                        '/projects',
                        projectId(),
                        'documents',
                        req.document_id || documentId(),
                      ]"
                      [queryParams]="{ highlight: req.source_section_id }"
                    >
                      <mat-icon aria-hidden="true">visibility</mat-icon>
                      Podgląd
                    </a>
                  </div>

                  @if (editingReqId() === req.req_id) {
                    <div class="req-edit">
                      <mat-form-field
                        appearance="outline"
                        class="edit-text-field"
                      >
                        <mat-label>Treść wymagania</mat-label>
                        <textarea
                          matInput
                          rows="3"
                          [value]="editText()"
                          (input)="editText.set($any($event.target).value)"
                        ></textarea>
                      </mat-form-field>
                      <mat-form-field
                        appearance="outline"
                        class="edit-priority-field"
                      >
                        <mat-label>Priorytet</mat-label>
                        <mat-select
                          [value]="editPriority()"
                          (selectionChange)="
                            editPriority.set($any($event).value)
                          "
                        >
                          <mat-option value="">Brak</mat-option>
                          <mat-option value="critical">Krytyczny</mat-option>
                          <mat-option value="high">Wysoki</mat-option>
                          <mat-option value="medium">Średni</mat-option>
                          <mat-option value="low">Niski</mat-option>
                        </mat-select>
                      </mat-form-field>
                      <div class="req-edit-actions">
                        <button
                          mat-flat-button
                          color="primary"
                          (click)="saveEdit(req)"
                          title="Zapisz zmiany"
                        >
                          <mat-icon aria-hidden="true">save</mat-icon>
                          Zapisz
                        </button>
                        <button
                          mat-button
                          (click)="cancelEdit()"
                          title="Anuluj"
                        >
                          <mat-icon aria-hidden="true">close</mat-icon>
                          Anuluj
                        </button>
                      </div>
                    </div>
                  } @else {
                    <div class="req-actions">
                      @if (!req.accepted && !req.rejected) {
                        <button
                          mat-button
                          color="primary"
                          (click)="acceptRequirement(req)"
                          title="Akceptuj wymaganie"
                        >
                          <mat-icon aria-hidden="true">check</mat-icon>
                        </button>
                        <button
                          mat-button
                          color="warn"
                          (click)="rejectRequirement(req)"
                          title="Odrzuć wymaganie"
                        >
                          <mat-icon aria-hidden="true">close</mat-icon>
                        </button>
                        <button
                          mat-button
                          (click)="editRequirement(req)"
                          title="Edytuj wymaganie"
                        >
                          <mat-icon aria-hidden="true">edit</mat-icon>
                        </button>
                      } @else if (req.accepted) {
                        <button
                          mat-button
                          color="primary"
                          disabled
                          title="Zaakceptowane"
                        >
                          <mat-icon aria-hidden="true">check_circle</mat-icon>
                          Zaakceptowane
                        </button>
                        <button
                          mat-button
                          (click)="undoDecision(req)"
                          title="Cofnij decyzję"
                        >
                          <mat-icon aria-hidden="true">undo</mat-icon>
                        </button>
                      } @else {
                        <button
                          mat-button
                          color="warn"
                          disabled
                          title="Odrzucone"
                        >
                          <mat-icon aria-hidden="true">cancel</mat-icon>
                          Odrzucone
                        </button>
                        <button
                          mat-button
                          (click)="undoDecision(req)"
                          title="Cofnij decyzję"
                        >
                          <mat-icon aria-hidden="true">undo</mat-icon>
                        </button>
                      }
                    </div>
                  }
                </div>
              }
            </div>
          } @else if (requirements().length === 0) {
            <div class="empty-state">
              <mat-icon aria-hidden="true">fact_check</mat-icon>
              <p>Brak wymagań do wyświetlenia.</p>
              <button
                mat-button
                color="primary"
                [routerLink]="['/projects', projectId(), 'documents']"
              >
                Wróć do dokumentów
              </button>
            </div>
          } @else {
            <div class="empty-state">
              <mat-icon aria-hidden="true">search_off</mat-icon>
              <p>Brak wymagań spełniających kryteria filtru.</p>
              <button mat-button (click)="clearFilters()">
                Wyczyść filtry
              </button>
            </div>
          }
        }

        <!-- Action Bar -->
        @if (filteredRequirements().length > 0) {
          <div class="action-bar">
            <button mat-button color="primary">
              <mat-icon aria-hidden="true">play_arrow</mat-icon>
              Generuj testy
            </button>
            <button mat-button>
              <mat-icon aria-hidden="true">download</mat-icon>
              Eksportuj
            </button>
            <button mat-button>
              <mat-icon aria-hidden="true">compare_arrows</mat-icon>
              Porównaj z kodem
            </button>
          </div>
        }
      </main>

      <app-footer />
    </div>
  `,
  styles: [
    `
      .doc-badge {
        font-size: 11px;
        color: #4b5563;
        background: #f3f4f6;
        border: 1px solid #d1d5db;
        border-radius: 6px;
        padding: 1px 6px;
        margin-left: 4px;
      }
      .view-page {
        min-height: 100vh;
        background: #f7f8fa;
        display: flex;
        flex-direction: column;
      }

      .view-content {
        flex: 1;
        padding: 32px 48px;
        max-width: 1200px;
        width: 100%;
        margin: 0 auto;
      }

      .page-header {
        margin-bottom: 24px;
      }

      .back-link {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        margin-bottom: 16px;
      }

      .header-info {
        display: flex;
        align-items: center;
        gap: 16px;
      }

      .page-title {
        font-size: 24px;
        font-weight: 700;
        color: #1a1a1a;
        margin: 0;
      }

      .badge {
        padding: 6px 14px;
        background: #dbeafe;
        color: #1e40af;
        border-radius: 20px;
        font-size: 13px;
        font-weight: 500;
      }

      .loading {
        display: flex;
        align-items: center;
        gap: 12px;
        color: #6b7280;
      }

      .filters {
        display: flex;
        gap: 16px;
        align-items: center;
        margin-bottom: 24px;
        flex-wrap: wrap;
      }

      .filter-field {
        width: 200px;
      }

      .search-field {
        flex: 1;
        min-width: 250px;
      }

      .stats {
        display: flex;
        gap: 20px;
        margin-left: auto;
      }

      .stat {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
        color: #6b7280;
      }

      .stat mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
      }

      .requirements-list {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }

      .requirement-card {
        background: #ffffff;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        transition: box-shadow 0.2s ease;
      }

      .requirement-card:hover {
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
      }

      .requirement-card.accepted {
        border-left: 4px solid #10b981;
      }

      .requirement-card.rejected {
        border-left: 4px solid #ef4444;
        opacity: 0.7;
      }

      .req-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 12px;
      }

      .req-id-type {
        display: flex;
        align-items: center;
        gap: 10px;
      }

      .req-id {
        font-weight: 600;
        color: #1e40af;
        font-size: 14px;
      }

      .type-chip {
        min-height: 24px;
      }

      .priority-critical {
        background: #fdecea;
        color: #611a15;
      }

      .priority-high {
        background: #fed7aa;
        color: #7c2708;
      }

      .priority-medium {
        background: #d1fae5;
        color: #065f46;
      }

      .priority-low {
        background: #e5e7eb;
        color: #374151;
      }

      .req-confidence {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 13px;
        color: #6b7280;
      }

      .confidence-icon {
        font-size: 16px;
        width: 16px;
        height: 16px;
      }

      .method {
        margin-left: 8px;
        padding: 2px 8px;
        background: #f3f4f6;
        border-radius: 4px;
        font-size: 11px;
        text-transform: uppercase;
      }

      .req-content {
        margin-bottom: 16px;
      }

      .req-text {
        margin: 0;
        color: #374151;
        line-height: 1.6;
      }

      .req-reasoning {
        display: flex;
        align-items: flex-start;
        gap: 8px;
        padding: 12px;
        background: #f5f3ff;
        border-left: 3px solid #8b5cf6;
        border-radius: 8px;
        font-size: 13px;
        color: #5b21b6;
        margin-bottom: 12px;
      }

      .req-reasoning mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
        color: #7c3aed;
        flex-shrink: 0;
      }

      .reasoning-body {
        display: flex;
        flex-direction: column;
        gap: 2px;
      }

      .reasoning-label {
        font-weight: 600;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: #6d28d9;
      }

      .reasoning-text {
        margin: 0;
        line-height: 1.5;
      }

      .req-source {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 12px;
        background: #f9fafb;
        border-radius: 8px;
        font-size: 13px;
        color: #6b7280;
        margin-bottom: 12px;
      }

      .req-source mat-icon {
        font-size: 16px;
        width: 16px;
        height: 16px;
      }

      .view-link {
        margin-left: auto;
      }

      .req-actions {
        display: flex;
        gap: 8px;
        padding-top: 12px;
        border-top: 1px solid #e5e7eb;
      }

      .req-edit {
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding-top: 12px;
        border-top: 1px solid #e5e7eb;
      }

      .edit-text-field {
        width: 100%;
      }

      .edit-priority-field {
        width: 200px;
      }

      .req-edit-actions {
        display: flex;
        gap: 8px;
      }

      .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 16px;
        padding: 64px 32px;
        text-align: center;
        color: #6b7280;
      }

      .empty-state mat-icon {
        font-size: 64px;
        height: 64px;
        width: 64px;
        color: #d1d5db;
      }

      .action-bar {
        display: flex;
        gap: 12px;
        margin-top: 24px;
        padding-top: 24px;
        border-top: 1px solid #e5e7eb;
      }

      @media (max-width: 768px) {
        .view-content {
          padding: 16px;
        }

        .filters {
          flex-direction: column;
          align-items: stretch;
        }

        .filter-field,
        .search-field {
          width: 100%;
        }

        .stats {
          flex-wrap: wrap;
        }
      }
    `,
  ],
})
export class RequirementListComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly documentService = inject(DocumentAnalysisService);

  // Signals
  readonly requirements = signal<Requirement[]>([]);
  readonly isLoading = signal(false);
  readonly documentTitle = signal("");
  readonly documentId = signal("");
  readonly searchQuery = signal("");
  readonly selectedType = signal("all");
  readonly selectedPriority = signal("all");

  // Inline edit state (Story 2.4 — AC5 edit)
  readonly editingReqId = signal<string | null>(null);
  readonly editText = signal("");
  readonly editPriority = signal<string>("");

  // Query params for document ID
  readonly documentIdFromQuery = computed(
    () => this.route.snapshot.queryParamMap.get("documentId") || "",
  );

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  readonly filteredRequirements = computed(() => {
    let reqs = this.requirements();

    // Type filter
    if (this.selectedType() !== "all") {
      reqs = reqs.filter((r) => r.type === this.selectedType());
    }

    // Priority filter
    if (this.selectedPriority() !== "all") {
      reqs = reqs.filter((r) => r.priority === this.selectedPriority());
    }

    // Search filter
    const query = this.searchQuery().toLowerCase().trim();
    if (query) {
      reqs = reqs.filter(
        (r) =>
          r.text.toLowerCase().includes(query) ||
          r.req_id.toLowerCase().includes(query) ||
          r.source_section_title.toLowerCase().includes(query),
      );
    }

    return reqs;
  });

  readonly totalRequirements = computed(() => this.requirements().length);
  readonly acceptedCount = computed(
    () => this.requirements().filter((r) => r.accepted).length,
  );
  readonly rejectedCount = computed(
    () => this.requirements().filter((r) => r.rejected).length,
  );
  readonly pendingCount = computed(
    () => this.requirements().filter((r) => !r.accepted && !r.rejected).length,
  );

  ngOnInit(): void {
    // Load document ID from query params or route
    const docId =
      this.documentIdFromQuery() ||
      this.route.snapshot.queryParams["documentId"];

    if (docId) {
      this.documentId.set(docId);
      this.loadRequirements(docId);
    } else {
      // Widok nawigacji projektu (bez documentId): agregacja wszystkich
      // dokumentów projektu — każdy wiersz niesie dokument źródłowy.
      this.loadProjectRequirements();
    }
  }

  /** true, gdy listujemy wszystkie dokumenty projektu (bez documentId). */
  readonly isProjectView = computed(() => this.documentId() === "");

  private loadProjectRequirements(): void {
    this.isLoading.set(true);
    this.documentService.getProjectRequirements(this.projectId()).subscribe({
      next: (response) => {
        this.documentTitle.set(`Wszystkie dokumenty (${response.documents})`);
        this.requirements.set(
          response.requirements.map((req) => this.toRow(req)),
        );
        this.isLoading.set(false);
      },
      error: (err) => {
        console.error("Failed to load project requirements:", err);
        this.isLoading.set(false);
      },
    });
  }

  private toRow(req: ApiRequirement): Requirement {
    const status = req.status || "extracted";
    return {
      req_id: req.reqId,
      document_id: req.documentId,
      document_filename: req.documentFilename ?? null,
      text: req.text,
      type: req.type,
      priority: (req.priority || null) as Requirement["priority"],
      source_section_id: req.sourceSectionId || "",
      // Tytuł rozdziału źródłowego; gdy ekstrakcja nie ustawiła ani tytułu,
      // ani id sekcji — etykieta zastępcza, żeby przy ikonie lokalizacji
      // nie wisiało puste pole (UI bug: pusta etykieta rozdziału).
      source_section_title:
        req.sourceSectionTitle || req.sourceSectionId || "Nieznana sekcja",
      confidence: req.confidence,
      extraction_method: (req.extractionMethod ||
        "native") as Requirement["extraction_method"],
      reasoning: req.reasoning ?? null,
      status,
      accepted: status === "accepted",
      rejected: status === "rejected",
    };
  }

  private loadRequirements(documentId: string): void {
    this.isLoading.set(true);

    this.documentService.getRequirements(documentId).subscribe({
      next: (response) => {
        this.documentTitle.set(response.filename);

        // Convert API requirements to component format
        this.requirements.set(
          response.requirements.map((req: ApiRequirement) => this.toRow(req)),
        );
        this.isLoading.set(false);
      },
      error: (err) => {
        console.error("Failed to load requirements:", err);
        this.isLoading.set(false);
      },
    });
  }

  onFilterChange(): void {
    // Filter changes are handled via computed signals
  }

  clearFilters(): void {
    this.selectedType.set("all");
    this.selectedPriority.set("all");
    this.searchQuery.set("");
  }

  acceptRequirement(req: Requirement): void {
    this.documentService
      .acceptRequirement(req.document_id || this.documentId(), req.req_id)
      .subscribe({
        next: () =>
          req.document_id
            ? this.loadProjectRequirements()
            : this.loadRequirements(this.documentId()),
        error: (err) => console.error("Failed to accept requirement:", err),
      });
  }

  rejectRequirement(req: Requirement): void {
    this.documentService
      .rejectRequirement(req.document_id || this.documentId(), req.req_id)
      .subscribe({
        next: () =>
          req.document_id
            ? this.loadProjectRequirements()
            : this.loadRequirements(this.documentId()),
        error: (err) => console.error("Failed to reject requirement:", err),
      });
  }

  undoDecision(req: Requirement): void {
    // Undo = reset workflow status back to "extracted"
    this.documentService
      .updateRequirement(req.document_id || this.documentId(), req.req_id, {
        status: "extracted",
      })
      .subscribe({
        next: () =>
          req.document_id
            ? this.loadProjectRequirements()
            : this.loadRequirements(this.documentId()),
        error: (err) => console.error("Failed to undo decision:", err),
      });
  }

  editRequirement(req: Requirement): void {
    // Inline edit mode (AC5) — opens an editable form within the card.
    this.editingReqId.set(req.req_id);
    this.editText.set(req.text);
    this.editPriority.set(req.priority || "");
  }

  cancelEdit(): void {
    this.editingReqId.set(null);
    this.editText.set("");
    this.editPriority.set("");
  }

  saveEdit(req: Requirement): void {
    const body: Record<string, string> = {};
    const text = this.editText().trim();
    const priority = this.editPriority();
    if (text && text !== req.text) {
      body["text"] = text;
    }
    if (priority && priority !== req.priority) {
      body["priority"] = priority;
    }
    if (Object.keys(body).length === 0) {
      this.cancelEdit();
      return;
    }

    this.documentService
      .updateRequirement(req.document_id || this.documentId(), req.req_id, body)
      .subscribe({
        next: () => {
          this.cancelEdit();
          this.loadRequirements(this.documentId());
        },
        error: (err) => console.error("Failed to update requirement:", err),
      });
  }

  getPriorityLabel(priority: string): string {
    const labels: Record<string, string> = {
      critical: "Krytyczny",
      high: "Wysoki",
      medium: "Średni",
      low: "Niski",
    };
    return labels[priority] || priority;
  }

  getConfidenceIcon(confidence: number): string {
    if (confidence >= 90) return "check_circle";
    if (confidence >= 70) return "info";
    return "help_outline";
  }
}
