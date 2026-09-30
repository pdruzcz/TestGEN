import { Component, inject, signal, computed, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { DestroyRef } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatSelectModule } from "@angular/material/select";
import { MatChipsModule } from "@angular/material/chips";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { NavbarComponent } from "../../../shared/components/navbar.component";
import { FooterComponent } from "../../../shared/components/footer.component";
import {
  CodeMapping,
  DocumentAnalysisService,
  GlossaryTerm,
  GlossaryTermUpdate,
} from "../../../services/document-analysis.service";

type TermType = GlossaryTerm["termType"];

@Component({
  selector: "app-glossary-list",
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatIconModule,
    MatInputModule,
    MatFormFieldModule,
    MatSelectModule,
    MatChipsModule,
    MatCheckboxModule,
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
            [routerLink]="['/projects', projectId(), 'requirements']"
            class="back-link"
          >
            <mat-icon>arrow_back</mat-icon>
            Wróć do wymagań
          </a>

          @if (documentTitle()) {
            <div class="header-info">
              <h1 class="page-title">Glosariusz: {{ documentTitle() }}</h1>
              <div class="badge">{{ terms().length }} terminów</div>
            </div>
          }

          @if (isLoading()) {
            <div class="loading" role="status" aria-live="polite">
              <mat-spinner diameter="24" aria-label="Ładowanie"></mat-spinner>
              <span>Ładowanie glosariusza…</span>
            </div>
          }
        </div>

        <!-- Filters -->
        @if (!isLoading() && terms().length > 0) {
          <div class="filters">
            <mat-form-field appearance="outline" class="filter-field">
              <mat-icon matPrefix>filter_list</mat-icon>
              <mat-label>Typ</mat-label>
              <mat-select
                [(value)]="selectedType"
                (selectionChange)="onFilterChange()"
              >
                <mat-option value="all">Wszystkie</mat-option>
                <mat-option value="domain">Dziedzina</mat-option>
                <mat-option value="technical">Techniczny</mat-option>
                <mat-option value="business">Biznesowy</mat-option>
                <mat-option value="acronym">Akronim</mat-option>
              </mat-select>
            </mat-form-field>

            <mat-form-field appearance="outline" class="search-field">
              <mat-icon matPrefix>search</mat-icon>
              <input
                matInput
                placeholder="Szukaj terminów…"
                [value]="searchQuery()"
                (input)="searchQuery.set($any($event.target).value)"
              />
            </mat-form-field>

            @if (!isProjectView()) {
              <button
                mat-flat-button
                color="primary"
                (click)="mapToCode()"
                [disabled]="isMapping()"
                title="Zmapuj terminy na byty kodu projektu"
              >
                <mat-icon aria-hidden="true">hub</mat-icon>
                Mapuj na kod
              </button>
            }
          </div>
        }

        <!-- Terms List -->
        @if (!isLoading()) {
          @if (filteredTerms().length > 0) {
            <div class="terms-list">
              @for (term of filteredTerms(); track term.term) {
                <div class="term-card" [class.verified]="term.isVerified">
                  <div class="term-header">
                    <div class="term-title">
                      <span class="term-name">{{ term.term }}</span>
                      <mat-chip
                        class="type-chip"
                        [class]="'type-' + term.termType"
                      >
                        {{ typeLabel(term.termType) }}
                      </mat-chip>
                      <mat-chip class="occ-chip">
                        <mat-icon aria-hidden="true">format_quote</mat-icon>
                        {{ term.occurrencesCount }} wystąpień
                      </mat-chip>
                    </div>
                    @if (term.isVerified) {
                      <mat-icon
                        aria-hidden="true"
                        class="verified-icon"
                        title="Zweryfikowany"
                      >
                        verified
                      </mat-icon>
                    }
                  </div>

                  <!-- Definition (inline-editable) -->
                  @if (editingTerm() === term.term) {
                    <div class="term-edit">
                      <span class="field-label">Definicja (edytowana)</span>
                      <mat-form-field appearance="outline" class="edit-field">
                        <textarea
                          matInput
                          rows="3"
                          [value]="editDefinitionText()"
                          (input)="
                            editDefinitionText.set($any($event.target).value)
                          "
                        ></textarea>
                      </mat-form-field>
                      <div class="edit-actions">
                        <button
                          mat-flat-button
                          color="primary"
                          (click)="saveEdit(term)"
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
                    <div class="term-definition">
                      <span class="field-label">Definicja</span>
                      @if (term.definition) {
                        <p class="definition-text">{{ term.definition }}</p>
                      } @else {
                        <p class="no-definition">Brak definicji</p>
                      }
                    </div>
                  }

                  <!-- Code mappings -->
                  <div class="term-mappings">
                    <span class="field-label">Mapowanie na kod</span>
                    @if (term.codeMappings?.length) {
                      <div class="mappings-list">
                        @for (
                          mapping of visibleMappings(term);
                          track mapping.name
                        ) {
                          <div class="mapping-row">
                            <mat-checkbox
                              [checked]="mapping.isConfirmed"
                              (change)="
                                toggleMapping(
                                  term,
                                  mapping,
                                  $any($event).checked
                                )
                              "
                              title="Potwierdź mapowanie"
                            ></mat-checkbox>
                            <span class="mapping-name">{{ mapping.name }}</span>
                            <span class="mapping-type">{{
                              typeTagLabel(mapping.type)
                            }}</span>
                            <span
                              class="mapping-similarity"
                              [class]="
                                'sim-' + similarityLevel(mapping.similarity)
                              "
                              title="Podobieństwo"
                            >
                              {{ (mapping.similarity * 100).toFixed(0) }}%
                            </span>
                          </div>
                        }
                        @if (hiddenMappingsCount(term) > 0) {
                          <span class="more-mappings">
                            +{{ hiddenMappingsCount(term) }} więcej
                          </span>
                        }
                      </div>
                    } @else {
                      <p class="no-mappings">Brak mapowań na kod</p>
                    }
                  </div>

                  <!-- Actions -->
                  @if (editingTerm() !== term.term) {
                    <div class="term-actions">
                      <button
                        mat-button
                        (click)="startEdit(term)"
                        title="Edytuj definicję"
                      >
                        <mat-icon aria-hidden="true">edit</mat-icon>
                        Edytuj definicję
                      </button>
                      <button
                        mat-button
                        (click)="toggleVerified(term)"
                        [title]="
                          term.isVerified
                            ? 'Cofnij weryfikację'
                            : 'Oznacz jako zweryfikowany'
                        "
                      >
                        <mat-icon aria-hidden="true">{{
                          term.isVerified ? "undo" : "check_circle"
                        }}</mat-icon>
                        {{
                          term.isVerified ? "Cofnij weryfikację" : "Zweryfikuj"
                        }}
                      </button>
                    </div>
                  }
                </div>
              }
            </div>
          } @else if (terms().length === 0) {
            <div class="empty-state">
              <mat-icon aria-hidden="true">menu_book</mat-icon>
              <p>Brak glosariusza dla tego dokumentu.</p>
              <p class="hint">
                Glosariusz tworzony jest z sekcji „Glosariusz" lub „Definicje".
              </p>
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
              <p>Brak terminów spełniających kryteria filtru.</p>
              <button mat-button (click)="clearFilters()">
                Wyczyść filtry
              </button>
            </div>
          }
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
        margin-right: 6px;
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

      .terms-list {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }

      .term-card {
        background: #ffffff;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        display: flex;
        flex-direction: column;
        gap: 12px;
      }

      .term-card.verified {
        border-left: 4px solid #10b981;
      }

      .term-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .term-title {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
      }

      .term-name {
        font-weight: 700;
        font-size: 18px;
        color: #1a1a1a;
      }

      .type-chip {
        min-height: 24px;
        font-size: 12px;
      }

      .type-domain {
        background: #e8f5e9;
        color: #1b5e20;
      }

      .type-technical {
        background: #fff8e1;
        color: #b26a00;
      }

      .type-business {
        background: #eceff1;
        color: #455a64;
      }

      .type-acronym {
        background: #e3f2fd;
        color: #0d47a1;
      }

      .occ-chip {
        min-height: 24px;
        background: #f3f4f6;
        color: #4b5563;
        font-size: 12px;
      }

      .occ-chip mat-icon {
        font-size: 14px;
        width: 14px;
        height: 14px;
      }

      .verified-icon {
        color: #10b981;
      }

      .field-label {
        display: block;
        font-size: 12px;
        font-weight: 500;
        color: #5a6270;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 4px;
      }

      .term-definition {
        display: flex;
        flex-direction: column;
      }

      .definition-text {
        margin: 0;
        color: #4b5563;
        line-height: 1.6;
        font-size: 15px;
      }

      .no-definition {
        margin: 0;
        color: #9ca3af;
        font-style: italic;
        font-size: 14px;
      }

      .term-edit {
        display: flex;
        flex-direction: column;
      }

      .edit-field {
        width: 100%;
      }

      .edit-actions {
        display: flex;
        gap: 8px;
      }

      .term-mappings {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }

      .mappings-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }

      .mapping-row {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 8px 12px;
        background: #f9fafb;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
      }

      .mapping-name {
        font-weight: 500;
        color: #1a1a1a;
        font-size: 14px;
      }

      .mapping-type {
        font-size: 11px;
        color: #6b7280;
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 9999px;
        padding: 2px 8px;
      }

      .mapping-similarity {
        margin-left: auto;
        font-size: 12px;
        font-weight: 500;
      }

      .sim-high {
        color: #1b5e20;
      }

      .sim-medium {
        color: #b26a00;
      }

      .sim-low {
        color: #6b7280;
      }

      .more-mappings {
        font-size: 12px;
        color: #1976d2;
        font-weight: 500;
        padding: 4px 12px;
      }

      .no-mappings {
        margin: 0;
        color: #9ca3af;
        font-style: italic;
        font-size: 14px;
      }

      .term-actions {
        display: flex;
        gap: 8px;
        padding-top: 12px;
        border-top: 1px solid #e5e7eb;
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

      .hint {
        color: #9ca3af;
        font-size: 14px;
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
      }
    `,
  ],
})
export class GlossaryListComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly documentService = inject(DocumentAnalysisService);

  readonly terms = signal<GlossaryTerm[]>([]);
  readonly isLoading = signal(false);
  readonly isMapping = signal(false);
  readonly documentTitle = signal("");
  readonly documentId = signal("");
  readonly searchQuery = signal("");
  readonly selectedType = signal<TermType | "all">("all");

  // Inline edit state (AC5).
  readonly editingTerm = signal<string | null>(null);
  readonly editDefinitionText = signal("");

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  readonly filteredTerms = computed(() => {
    let list = this.terms();
    if (this.selectedType() !== "all") {
      list = list.filter((t) => t.termType === this.selectedType());
    }
    const query = this.searchQuery().toLowerCase().trim();
    if (query) {
      list = list.filter(
        (t) =>
          t.term.toLowerCase().includes(query) ||
          (t.definition ?? "").toLowerCase().includes(query) ||
          t.codeMappings.some((m) => m.name.toLowerCase().includes(query)),
      );
    }
    return list;
  });

  ngOnInit(): void {
    const docId =
      this.route.snapshot.queryParamMap.get("documentId") ||
      this.route.snapshot.queryParams["documentId"];
    if (docId) {
      this.documentId.set(docId);
      this.loadGlossary(docId);
    } else {
      // Widok nawigacji projektu: terminy ze wszystkich dokumentów projektu.
      this.loadProjectGlossary();
    }
  }

  /** true, gdy listujemy wszystkie dokumenty projektu (bez documentId). */
  readonly isProjectView = computed(() => this.documentId() === "");

  private loadProjectGlossary(): void {
    this.isLoading.set(true);
    this.documentService.getProjectGlossary(this.projectId()).subscribe({
      next: (response) => {
        this.documentTitle.set(`Wszystkie dokumenty (${response.documents})`);
        this.terms.set(response.terms || []);
        this.isLoading.set(false);
      },
      error: (err) => {
        console.error("Failed to load project glossary:", err);
        this.isLoading.set(false);
      },
    });
  }

  private loadGlossary(documentId: string): void {
    this.isLoading.set(true);
    this.documentService.getGlossary(documentId).subscribe({
      next: (response) => {
        this.documentTitle.set(response.filename || "Dokument");
        this.terms.set(response.terms || []);
        this.isLoading.set(false);
      },
      error: (err) => {
        console.error("Failed to load glossary:", err);
        this.isLoading.set(false);
      },
    });
  }

  onFilterChange(): void {
    // Filter changes are reflected via the computed signal.
  }

  clearFilters(): void {
    this.selectedType.set("all");
    this.searchQuery.set("");
  }

  typeLabel(type: TermType): string {
    const labels: Record<TermType, string> = {
      domain: "Dziedzina",
      technical: "Techniczny",
      business: "Biznesowy",
      acronym: "Akronim",
    };
    return labels[type] ?? type;
  }

  typeTagLabel(type: string): string {
    const labels: Record<string, string> = {
      function: "funkcja",
      method: "metoda",
      class: "klasa",
      module: "moduł",
    };
    return labels[type] ?? type;
  }

  similarityLevel(similarity: number): "high" | "medium" | "low" {
    if (similarity >= 0.8) return "high";
    if (similarity >= 0.5) return "medium";
    return "low";
  }

  visibleMappings(term: GlossaryTerm): CodeMapping[] {
    return (term.codeMappings ?? []).slice(0, 3);
  }

  hiddenMappingsCount(term: GlossaryTerm): number {
    return Math.max(0, (term.codeMappings ?? []).length - 3);
  }

  startEdit(term: GlossaryTerm): void {
    this.editingTerm.set(term.term);
    this.editDefinitionText.set(term.definition ?? "");
  }

  cancelEdit(): void {
    this.editingTerm.set(null);
    this.editDefinitionText.set("");
  }

  saveEdit(term: GlossaryTerm): void {
    const definition = this.editDefinitionText().trim() || undefined;
    this.documentService
      .updateGlossaryTerm(term.documentId || this.documentId(), term.term, {
        definition,
      })
      .subscribe({
        next: () => {
          this.cancelEdit();
          this.reload();
        },
        error: (err) => console.error("Failed to update glossary term:", err),
      });
  }

  toggleVerified(term: GlossaryTerm): void {
    const body: GlossaryTermUpdate = { isVerified: !term.isVerified };
    this.documentService
      .updateGlossaryTerm(term.documentId || this.documentId(), term.term, body)
      .subscribe({
        next: () => this.reload(),
        error: (err) => console.error("Failed to update glossary term:", err),
      });
  }

  toggleMapping(
    term: GlossaryTerm,
    mapping: CodeMapping,
    checked: boolean,
  ): void {
    const confirmed = term.codeMappings
      .filter((m) => (m === mapping ? checked : m.isConfirmed))
      .map((m) => m.name);
    this.documentService
      .updateGlossaryTerm(term.documentId || this.documentId(), term.term, {
        confirmedMappingIds: confirmed,
      })
      .subscribe({
        next: () => this.reload(),
        error: (err) => console.error("Failed to confirm mapping:", err),
      });
  }

  /** Odświeżenie listy wg aktualnego widoku (dokument vs projekt). */
  private reload(): void {
    this.isProjectView()
      ? this.loadProjectGlossary()
      : this.loadGlossary(this.documentId());
  }

  mapToCode(): void {
    this.isMapping.set(true);
    this.documentService.mapGlossaryToCode(this.documentId()).subscribe({
      next: (response) => {
        this.terms.set(response.terms || []);
        this.isMapping.set(false);
      },
      error: (err) => {
        console.error("Failed to map glossary to code:", err);
        this.isMapping.set(false);
      },
    });
  }
}
