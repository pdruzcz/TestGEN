import { Component, inject, signal, computed, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { DestroyRef } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatInputModule } from "@angular/material/input";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatTabsModule } from "@angular/material/tabs";
import { NavbarComponent } from "../../../shared/components/navbar.component";
import { FooterComponent } from "../../../shared/components/footer.component";
import {
  DocumentService,
  DocumentFile,
  ParsedDocument,
  DocumentSection,
  TableData,
} from "../services/document.service";

interface FlatSection extends DocumentSection {
  levelIndent: number;
  hasChildren: boolean;
}

@Component({
  selector: "app-document-view",
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatInputModule,
    MatFormFieldModule,
    MatTabsModule,
    RouterLink,
    NavbarComponent,
    FooterComponent,
  ],
  template: `
    <div class="view-page">
      <app-navbar activeLink="projects" />

      <main class="view-content" id="main-content" tabindex="-1">
        <!-- Header -->
        <div class="view-header">
          <a
            mat-button
            [routerLink]="['/projects', projectId()]"
            class="back-link"
          >
            <mat-icon>arrow_back</mat-icon>
            Wróć do dokumentacji
          </a>

          @if (isLoading()) {
            <div class="loading" role="status" aria-live="polite">
              <mat-spinner
                diameter="24"
                aria-label="Ładowanie dokumentu"
              ></mat-spinner>
              <span>Ładowanie dokumentu…</span>
            </div>
          } @else if (documentFile()) {
            <div class="document-header">
              <div class="document-meta">
                <mat-icon aria-hidden="true">{{
                  getDocIcon(documentFile()!)
                }}</mat-icon>
                <div class="meta-info">
                  <h1 class="document-title">{{ documentFile()!.filename }}</h1>
                  <div class="meta-badges">
                    <span class="badge">
                      {{ formatSize(documentFile()!.fileSize) }}
                    </span>
                    @if (documentFile()!.docFormat) {
                      <span class="badge format">
                        {{ documentFile()!.docFormat!.toUpperCase() }}
                      </span>
                    }
                    @if (documentFile()!.pageCount) {
                      <span class="badge">
                        {{ documentFile()!.pageCount }} stron
                      </span>
                    }
                    <span class="badge category">
                      {{
                        documentFile()!.fileCategory === "documentation"
                          ? "Dokumentacja"
                          : "Kod"
                      }}
                    </span>
                  </div>
                </div>
              </div>

              <div class="header-actions">
                <button
                  mat-button
                  color="primary"
                  [disabled]="!hasParsedData()"
                  (click)="startAnalysis()"
                >
                  <mat-icon aria-hidden="true">analytics</mat-icon>
                  Analizuj wymagania
                </button>
              </div>
            </div>
          }

          @if (error()) {
            <div class="error-banner" role="alert" aria-live="assertive">
              <mat-icon aria-hidden="true">error</mat-icon>
              {{ error() }}
            </div>
          }

          <!-- Analysis Navigation -->
          @if (!isLoading() && documentFile()) {
            <div class="analysis-nav">
              <h3 class="nav-title">Analiza dokumentu</h3>
              <div class="nav-buttons">
                <a
                  mat-button
                  class="nav-button"
                  [routerLink]="['/projects', projectId(), 'requirements']"
                  [queryParams]="{ documentId: documentId() }"
                >
                  <mat-icon aria-hidden="true">fact_check</mat-icon>
                  Wymagania
                </a>
                <a
                  mat-button
                  class="nav-button"
                  [routerLink]="['/projects', projectId(), 'glossary']"
                  [queryParams]="{ documentId: documentId() }"
                >
                  <mat-icon aria-hidden="true">menu_book</mat-icon>
                  Glosariusz
                </a>
                <a
                  mat-button
                  class="nav-button"
                  [routerLink]="['/projects', projectId(), 'inconsistencies']"
                  [queryParams]="{ documentId: documentId() }"
                >
                  <mat-icon aria-hidden="true">warning</mat-icon>
                  Niespójności
                </a>
                <a
                  mat-button
                  class="nav-button"
                  [routerLink]="['/projects', projectId(), 'gap-analysis']"
                  [queryParams]="{ documentId: documentId() }"
                >
                  <mat-icon aria-hidden="true">analytics</mat-icon>
                  Analiza pokrycia
                </a>
                <a
                  mat-button
                  class="nav-button"
                  [routerLink]="['/projects', projectId(), 'traceability']"
                  [queryParams]="{ documentId: documentId() }"
                >
                  <mat-icon aria-hidden="true">grid_on</mat-icon>
                  Traceability
                </a>
              </div>
            </div>
          }
        </div>

        <!-- Content -->
        @if (!isLoading() && parsedDocument()) {
          <div class="document-body">
            <!-- Sidebar Navigation -->
            <aside class="sidebar" aria-label="Nawigacja sekcji">
              <div class="sidebar-header">
                <h3>Sekcje</h3>
                <mat-form-field appearance="outline" class="search-field">
                  <mat-icon matPrefix>search</mat-icon>
                  <input
                    matInput
                    placeholder="Szukaj sekcji…"
                    [value]="searchQuery()"
                    (input)="searchQuery.set($any($event.target).value)"
                  />
                </mat-form-field>
              </div>

              <nav class="section-nav">
                @for (section of filteredSections(); track section.sectionId) {
                  <button
                    class="section-link"
                    [class.active]="activeSectionId() === section.sectionId"
                    [class.has-selected-child]="
                      hasSelectedChild(section.sectionId)
                    "
                    [style.padding-left.px]="8 + section.levelIndent * 12"
                    (click)="scrollToSection(section.sectionId)"
                    [attr.aria-label]="'Przejdź do sekcji: ' + section.title"
                  >
                    @if (section.hasChildren) {
                      <mat-icon class="expand-icon" aria-hidden="true"
                        >expand_more</mat-icon
                      >
                    }
                    <span class="section-label">{{ section.title }}</span>
                  </button>
                }
              </nav>

              @if (tables().length > 0) {
                <div class="sidebar-section">
                  <h3>Tabele ({{ tables().length }})</h3>
                  <nav class="table-nav">
                    @for (table of tables(); track table.tableId) {
                      <button
                        class="table-link"
                        [class.active]="activeTableId() === table.tableId"
                        (click)="scrollToTable(table.tableId)"
                        [attr.aria-label]="
                          'Przejdź do tabeli: ' + table.tableId
                        "
                      >
                        <mat-icon aria-hidden="true">table_chart</mat-icon>
                        <span>Tabela {{ table.tableId.slice(0, 8) }}</span>
                      </button>
                    }
                  </nav>
                </div>
              }
            </aside>

            <!-- Main Content -->
            <main class="main-content" tabindex="-1">
              <!-- Raw Text Tab -->
              @if (parsedDocument()) {
                <mat-tab-group>
                  <mat-tab label="Sekcje">
                    <div class="sections-container">
                      @for (
                        section of flatSections();
                        track section.sectionId
                      ) {
                        <section
                          [id]="'section-' + section.sectionId"
                          class="document-section"
                          [class.highlighted]="
                            highlightSectionId() === section.sectionId
                          "
                          [attr.aria-label]="'Sekcja: ' + section.title"
                        >
                          @switch (section.level) {
                            @case (1) {
                              <h1 [class]="'section-h' + section.level">
                                {{ section.title }}
                              </h1>
                            }
                            @case (2) {
                              <h2 [class]="'section-h' + section.level">
                                {{ section.title }}
                              </h2>
                            }
                            @case (3) {
                              <h3 [class]="'section-h' + section.level">
                                {{ section.title }}
                              </h3>
                            }
                            @case (4) {
                              <h4 [class]="'section-h' + section.level">
                                {{ section.title }}
                              </h4>
                            }
                            @case (5) {
                              <h5 [class]="'section-h' + section.level">
                                {{ section.title }}
                              </h5>
                            }
                            @default {
                              <h6 [class]="'section-h' + section.level">
                                {{ section.title }}
                              </h6>
                            }
                          }
                          <div class="section-content">
                            {{ section.content }}
                          </div>
                        </section>
                      }

                      @if (flatSections().length === 0) {
                        <p class="empty-state">Brak sekcji w dokumencie.</p>
                      }
                    </div>
                  </mat-tab>

                  @if (parsedDocument()!.rawText) {
                    <mat-tab label="Surowy tekst">
                      <div class="raw-text-container">
                        <pre class="raw-text">{{
                          parsedDocument()!.rawText
                        }}</pre>
                      </div>
                    </mat-tab>
                  }

                  @if (tables().length > 0) {
                    <mat-tab label="Tabele">
                      <div class="tables-container">
                        @for (table of tables(); track table.tableId) {
                          <div
                            [id]="'table-' + table.tableId"
                            class="table-wrapper"
                          >
                            <h4 class="table-title">
                              Tabela {{ table.tableId.slice(0, 8) }}
                            </h4>
                            <div class="table-scroll">
                              <table class="styled-table">
                                <thead>
                                  <tr>
                                    @for (
                                      header of table.headers;
                                      track header
                                    ) {
                                      <th>{{ header || "Kol." }}</th>
                                    }
                                  </tr>
                                </thead>
                                <tbody>
                                  @for (row of table.rows; track $index) {
                                    <tr>
                                      @for (cell of row; track cell) {
                                        <td>{{ cell }}</td>
                                      }
                                    </tr>
                                  }
                                </tbody>
                              </table>
                            </div>
                          </div>
                        }
                      </div>
                    </mat-tab>
                  }
                </mat-tab-group>
              }
            </main>
          </div>
        } @else if (!isLoading() && !error()) {
          @if (parsedDocument()) {
            <div class="empty-state">
              <mat-icon aria-hidden="true">description</mat-icon>
              <p>Dokument nie zawiera sekcji.</p>
            </div>
          } @else {
            <div class="empty-state">
              <mat-icon aria-hidden="true">description</mat-icon>
              <p>Dokument nie został jeszcze zaparsowany.</p>
              <button
                mat-button
                color="primary"
                [routerLink]="['/projects', projectId(), 'documents']"
              >
                Wróć do listy dokumentów
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
      .view-page {
        min-height: 100vh;
        background: #f7f8fa;
        display: flex;
        flex-direction: column;
      }

      .view-content {
        flex: 1;
        padding: 32px 48px;
        max-width: 1400px;
        width: 100%;
        margin: 0 auto;
      }

      .view-header {
        margin-bottom: 24px;
      }

      .back-link {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        margin-bottom: 16px;
      }

      .loading {
        display: flex;
        align-items: center;
        gap: 12px;
        color: #6b7280;
        padding: 16px 0;
      }

      .document-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 24px;
      }

      .document-meta {
        display: flex;
        align-items: center;
        gap: 16px;
      }

      .document-meta mat-icon {
        font-size: 48px;
        height: 48px;
        width: 48px;
        color: #6b7280;
      }

      .meta-info {
        flex: 1;
      }

      .document-title {
        font-size: 24px;
        font-weight: 700;
        color: #1a1a1a;
        margin: 0 0 8px 0;
      }

      .meta-badges {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
      }

      .badge {
        display: inline-flex;
        align-items: center;
        padding: 4px 10px;
        background: #e5e7eb;
        border-radius: 16px;
        font-size: 12px;
        font-weight: 500;
        color: #374151;
      }

      .badge.format {
        background: #dbeafe;
        color: #1e40af;
      }

      .badge.category {
        background: #d1fae5;
        color: #065f46;
      }

      .header-actions {
        display: flex;
        gap: 8px;
      }

      .error-banner {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 12px 16px;
        background: #fdecea;
        color: #611a15;
        border-radius: 8px;
        margin-top: 16px;
      }

      .analysis-nav {
        margin-top: 24px;
        padding: 20px;
        background: #f0f9ff;
        border: 1px solid #bae6fd;
        border-radius: 12px;
      }

      .nav-title {
        font-size: 16px;
        font-weight: 600;
        color: #0c4a6e;
        margin: 0 0 16px 0;
      }

      .nav-buttons {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
      }

      .nav-button {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: #ffffff;
        border: 1px solid #7dd3fc;
        border-radius: 8px;
        padding: 10px 16px;
        text-decoration: none;
        color: #0369a1;
        font-weight: 500;
        transition: all 0.2s ease;
      }

      .nav-button:hover {
        background: #e0f2fe;
        border-color: #38bdf8;
        transform: translateY(-1px);
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
      }

      .nav-button mat-icon {
        font-size: 20px;
        height: 20px;
        width: 20px;
      }

      .document-body {
        display: grid;
        grid-template-columns: 280px 1fr;
        gap: 24px;
        background: #ffffff;
        border-radius: 16px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        height: calc(100vh - 280px);
        min-height: 500px;
      }

      .sidebar {
        background: #f9fafb;
        border-right: 1px solid #e5e7eb;
        overflow-y: auto;
        padding: 16px;
      }

      .sidebar-header {
        margin-bottom: 16px;
      }

      .sidebar-header h3 {
        font-size: 14px;
        font-weight: 600;
        color: #1a1a1a;
        margin: 0 0 8px 0;
      }

      .search-field {
        width: 100%;
      }

      .search-field .mat-mdc-form-field-subscript-wrapper {
        display: none;
      }

      .section-nav {
        display: flex;
        flex-direction: column;
        gap: 2px;
      }

      .section-link {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 8px 12px;
        border: none;
        background: transparent;
        text-align: left;
        font-size: 13px;
        color: #4b5563;
        cursor: pointer;
        border-radius: 6px;
        transition: background 0.15s ease;
        width: 100%;
      }

      .section-link:hover {
        background: #e5e7eb;
      }

      .section-link.active {
        background: #dbeafe;
        color: #1e40af;
        font-weight: 500;
      }

      .section-link.has-selected-child {
        color: #1e40af;
      }

      .expand-icon {
        font-size: 16px;
        width: 16px;
        height: 16px;
      }

      .section-label {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .sidebar-section {
        margin-top: 20px;
        padding-top: 16px;
        border-top: 1px solid #e5e7eb;
      }

      .sidebar-section h3 {
        font-size: 12px;
        font-weight: 600;
        color: #6b7280;
        margin: 0 0 8px 0;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }

      .table-nav {
        display: flex;
        flex-direction: column;
        gap: 2px;
      }

      .table-link {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 6px 12px;
        border: none;
        background: transparent;
        text-align: left;
        font-size: 12px;
        color: #4b5563;
        cursor: pointer;
        border-radius: 6px;
        transition: background 0.15s ease;
        width: 100%;
      }

      .table-link:hover {
        background: #e5e7eb;
      }

      .table-link.active {
        background: #dbeafe;
        color: #1e40af;
      }

      .table-link mat-icon {
        font-size: 16px;
        width: 16px;
        height: 16px;
      }

      .main-content {
        overflow-y: auto;
        padding: 24px 32px;
      }

      .sections-container {
        display: flex;
        flex-direction: column;
        gap: 24px;
      }

      .document-section {
        scroll-margin-top: 20px;
      }

      /* Sekcja źródłowa wymogu (?highlight=…) — podświetlenie „markerem". */
      .document-section.highlighted {
        background: #fefce8;
        border-left: 3px solid #eab308;
        border-radius: 8px;
        padding: 12px;
      }

      .document-section h1,
      .document-section h2,
      .document-section h3,
      .document-section h4,
      .document-section h5,
      .document-section h6 {
        color: #1a1a1a;
        margin: 0 0 12px 0;
      }

      .section-h1 {
        font-size: 28px;
        font-weight: 700;
      }
      .section-h2 {
        font-size: 24px;
        font-weight: 600;
      }
      .section-h3 {
        font-size: 20px;
        font-weight: 600;
      }
      .section-h4 {
        font-size: 18px;
        font-weight: 600;
      }
      .section-h5 {
        font-size: 16px;
        font-weight: 600;
      }
      .section-h6 {
        font-size: 14px;
        font-weight: 600;
      }

      .section-content {
        color: #374151;
        line-height: 1.7;
        white-space: pre-wrap;
      }

      .raw-text-container {
        background: #f9fafb;
        border-radius: 8px;
        padding: 16px;
      }

      .raw-text {
        margin: 0;
        font-family: "Courier New", monospace;
        font-size: 13px;
        color: #374151;
        white-space: pre-wrap;
        word-break: break-word;
      }

      .tables-container {
        display: flex;
        flex-direction: column;
        gap: 24px;
      }

      .table-wrapper {
        scroll-margin-top: 20px;
      }

      .table-title {
        font-size: 16px;
        font-weight: 600;
        color: #1a1a1a;
        margin: 0 0 12px 0;
      }

      .table-scroll {
        overflow-x: auto;
        max-width: 100%;
      }

      .styled-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
      }

      .styled-table th {
        background: #f9fafb;
        font-weight: 600;
        color: #1a1a1a;
        padding: 10px 12px;
        border: 1px solid #e5e7eb;
        text-align: left;
        white-space: nowrap;
      }

      .styled-table td {
        padding: 10px 12px;
        border: 1px solid #e5e7eb;
        color: #374151;
      }

      .styled-table tr:hover {
        background: #f9fafb;
      }

      .styled-table td,
      .styled-table th {
        max-width: 300px;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 16px;
        padding: 48px;
        text-align: center;
        color: #6b7280;
      }

      .empty-state mat-icon {
        font-size: 64px;
        height: 64px;
        width: 64px;
        color: #d1d5db;
      }

      @media (max-width: 1024px) {
        .document-body {
          grid-template-columns: 1fr;
          height: auto;
        }

        .sidebar {
          border-right: none;
          border-bottom: 1px solid #e5e7eb;
          max-height: 200px;
        }
      }

      @media (max-width: 768px) {
        .view-content {
          padding: 16px;
        }

        .document-header {
          flex-direction: column;
        }

        .header-actions {
          width: 100%;
        }
      }
    `,
  ],
})
export class DocumentViewComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly documentService = inject(DocumentService);

  // Signals
  readonly documentFile = signal<DocumentFile | null>(null);
  readonly parsedDocument = signal<ParsedDocument | null>(null);
  readonly isLoading = signal(false);
  readonly error = signal("");
  readonly searchQuery = signal("");
  readonly activeSectionId = signal("");
  readonly activeTableId = signal("");

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  readonly documentId = computed(
    () => this.route.snapshot.paramMap.get("documentId") ?? "",
  );

  /**
   * Sekcja źródłowa wymogu — parametr ``?highlight={sourceSectionId}``
   * przekazywany przez link „Podgląd" na liście wymagań.
   */
  readonly highlightSectionId = computed(
    () => this.route.snapshot.queryParamMap.get("highlight") || "",
  );

  // Flatten sections for navigation
  readonly flatSections = computed(() => {
    const doc = this.parsedDocument();
    if (!doc) return [];

    const flatten = (
      sections: DocumentSection[],
      level = 0,
      parentId: string | null = null,
    ): FlatSection[] => {
      const result: FlatSection[] = [];
      for (const section of sections) {
        result.push({
          ...section,
          levelIndent: level,
          hasChildren: section.content ? section.content.length > 50 : false,
        });
        if (section.content) {
          // Check for nested sections (would need child sections in data model)
        }
      }
      return result;
    };

    return flatten(doc.sections);
  });

  readonly sections = computed(() => this.parsedDocument()?.sections ?? []);
  readonly tables = computed(() => this.parsedDocument()?.tables ?? []);

  // Filter sections by search query
  readonly filteredSections = computed(() => {
    const query = this.searchQuery().toLowerCase();
    if (!query) return this.flatSections();

    return this.flatSections().filter(
      (s) =>
        s.title.toLowerCase().includes(query) ||
        s.content.toLowerCase().includes(query),
    );
  });

  ngOnInit(): void {
    if (this.projectId() && this.documentId()) {
      this.loadDocument();
    }
  }

  private loadDocument(): void {
    this.isLoading.set(true);
    this.error.set("");

    this.documentService
      .getDocumentDetail(this.projectId(), this.documentId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          this.documentFile.set(response.sourceFile);
          this.parsedDocument.set(response.parsedDocument);
          this.isLoading.set(false);
          this.applyHighlight();
        },
        error: (err) => {
          this.error.set(
            `Błąd ładowania dokumentu: ${err.message || "Nieznany błąd"}`,
          );
          this.isLoading.set(false);
        },
      });
  }

  scrollToSection(sectionId: string): void {
    this.activeSectionId.set(sectionId);
    this.scrollToElement(`section-${sectionId}`);
  }

  /**
   * Po załadowaniu dokumentu przewiń do sekcji źródłowej wymogu
   * (``?highlight=``). Sekcje renderują się dopiero po zmianie sygnałów,
   * więc scroll czeka jedną turę na wyrenderowany DOM.
   */
  private applyHighlight(): void {
    const sectionId = this.highlightSectionId();
    if (!sectionId || !this.parsedDocument()) return;

    setTimeout(() => {
      if (document.getElementById(`section-${sectionId}`)) {
        this.activeSectionId.set(sectionId);
        this.scrollToElement(`section-${sectionId}`);
      }
    });
  }

  /** Scroll do elementu; jsdom (testy) nie implementuje scrollIntoView. */
  private scrollToElement(elementId: string): void {
    const element = document.getElementById(elementId);
    if (element && typeof element.scrollIntoView === "function") {
      element.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  scrollToTable(tableId: string): void {
    this.activeTableId.set(tableId);
    this.scrollToElement(`table-${tableId}`);
  }

  hasSelectedChild(parentId: string): boolean {
    // Check if active section is a descendant of this section
    const active = this.activeSectionId();
    if (!active) return false;

    const activeSection = this.sections().find((s) => s.sectionId === active);
    return activeSection?.parentSectionId === parentId;
  }

  hasParsedData(): boolean {
    return !!this.parsedDocument();
  }

  startAnalysis(): void {
    // Navigate to analysis page
    // This would trigger requirement extraction
    console.log("Starting analysis for document:", this.documentId());
  }

  getDocIcon(doc: DocumentFile): string {
    switch (doc.docFormat) {
      case "pdf":
        return "picture_as_pdf";
      case "docx":
        return "description";
      case "md":
        return "code";
      case "html":
        return "language";
      case "txt":
        return "text_snippet";
      default:
        return "insert_drive_file";
    }
  }

  formatSize(bytes: number): string {
    if (!Number.isFinite(bytes) || bytes < 0) return "0 B";
    if (bytes < 1024) return `${bytes} B`;
    const kb = bytes / 1024;
    if (kb < 1024) return `${kb.toFixed(1)} KB`;
    const mb = kb / 1024;
    if (mb < 1024) return `${mb.toFixed(1)} MB`;
    return `${(mb / 1024).toFixed(2)} GB`;
  }
}
