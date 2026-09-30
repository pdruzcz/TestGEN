import {
  Component,
  computed,
  DestroyRef,
  inject,
  OnInit,
  signal,
} from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { CommonModule } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatChipsModule } from "@angular/material/chips";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatSidenavModule } from "@angular/material/sidenav";
import { MatTreeModule } from "@angular/material/tree";

import { FooterComponent } from "../../../shared/components/footer.component";
import { NavbarComponent } from "../../../shared/components/navbar.component";
import { DocSection, DocSectionsService } from "./doc-sections.service";

@Component({
  selector: "app-doc-sections",
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatChipsModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSidenavModule,
    MatTreeModule,
    RouterLink,
    NavbarComponent,
    FooterComponent,
  ],
  template: `
    <div class="view-page">
      <app-navbar activeLink="projects" />

      <mat-sidenav-container class="sections-container">
        <!-- Left: section tree -->
        <mat-sidenav
          mode="side"
          opened
          class="tree-sidenav"
          [disableClose]="true"
        >
          <div class="tree-header">
            <a
              mat-button
              [routerLink]="['/projects', projectId(), 'documents']"
              class="back-link"
            >
              <mat-icon>arrow_back</mat-icon>
              Wróć do dokumentów
            </a>
            @if (documentTitle()) {
              <h1 class="page-title">
                Sekcje dokumentu: {{ documentTitle() }}
              </h1>
            }
          </div>

          @if (isLoading()) {
            <div class="loading" role="status" aria-live="polite">
              <mat-spinner diameter="24" aria-label="Ładowanie"></mat-spinner>
              <span>Ładowanie…</span>
            </div>
          } @else if (sections().length === 0) {
            <div class="empty-state">
              <mat-icon aria-hidden="true">segment</mat-icon>
              <p>Brak sekcji do wyświetlenia.</p>
            </div>
          } @else {
            <mat-tree
              [dataSource]="sections()"
              [childrenAccessor]="childrenAccessor"
              class="section-tree"
            >
              <mat-tree-node *matTreeNodeDef="let node" matTreeNodePadding>
                <button
                  mat-icon-button
                  matTreeNodeToggle
                  [disabled]="!hasChildren(node)"
                  aria-label="Rozwiń lub zwiń sekcję"
                >
                  <mat-icon>{{
                    hasChildren(node) ? "expand_more" : "circle"
                  }}</mat-icon>
                </button>
                <button
                  mat-button
                  class="node-title"
                  [class.selected]="selectedId() === node.sectionId"
                  (click)="selectSection(node)"
                >
                  {{ node.title }}
                </button>
                <mat-chip
                  [ngClass]="'chip-' + node.sectionType"
                  class="type-chip"
                >
                  {{ typeLabel(node.sectionType) }}
                </mat-chip>
              </mat-tree-node>
            </mat-tree>
          }
        </mat-sidenav>

        <!-- Right: section content -->
        <mat-sidenav-content class="content-pane" role="main" id="main-content" tabindex="-1">
          @if (selectedSection(); as section) {
            <article class="section-detail">
              <header class="detail-header">
                <h2>{{ section.title }}</h2>
                <div class="meta">
                  <span class="meta-item">
                    <mat-icon aria-hidden="true">format_list_numbered</mat-icon>
                    Pozycja: {{ section.position + 1 }}
                  </span>
                  @if (section.pageNumber !== null) {
                    <span class="meta-item">
                      <mat-icon aria-hidden="true">description</mat-icon>
                      Strona: {{ section.pageNumber }}
                    </span>
                  }
                  <mat-chip [ngClass]="'chip-' + section.sectionType">
                    {{ typeLabel(section.sectionType) }}
                  </mat-chip>
                </div>
              </header>
              <pre class="section-content">{{ section.content }}</pre>
            </article>
          } @else {
            <div class="placeholder">
              <mat-icon aria-hidden="true">topic</mat-icon>
              <p>Wybierz sekcję z drzewa, aby zobaczyć jej treść.</p>
            </div>
          }
        </mat-sidenav-content>
      </mat-sidenav-container>

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

      .sections-container {
        flex: 1;
        min-height: 0;
      }

      .tree-sidenav {
        width: 420px;
        background: #ffffff;
        border-right: 1px solid #e5e7eb;
        overflow-y: auto;
      }

      .tree-header {
        position: sticky;
        top: 0;
        background: #ffffff;
        padding: 16px;
        border-bottom: 1px solid #e5e7eb;
        z-index: 1;
      }

      .back-link {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        margin-bottom: 8px;
      }

      .page-title {
        font-size: 18px;
        font-weight: 700;
        color: #1a1a1a;
        margin: 0;
      }

      .loading,
      .empty-state,
      .placeholder {
        display: flex;
        align-items: center;
        gap: 12px;
        color: #6b7280;
        padding: 32px 16px;
      }

      .empty-state {
        flex-direction: column;
        text-align: center;
      }

      .empty-state mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        color: #d1d5db;
      }

      .section-tree {
        padding: 8px;
      }

      .node-title {
        text-transform: none;
        text-align: left;
      }

      .node-title.selected {
        font-weight: 700;
        color: #1e40af;
      }

      .type-chip {
        min-height: 22px;
        font-size: 11px;
      }

      .chip-functional {
        background: #dbeafe;
        color: #1e40af;
      }

      .chip-non_functional {
        background: #ede9fe;
        color: #5b21b6;
      }

      .chip-instruction {
        background: #d1fae5;
        color: #065f46;
      }

      .chip-unclassified {
        background: #e5e7eb;
        color: #374151;
      }

      .content-pane {
        background: #f7f8fa;
        padding: 32px 48px;
      }

      .section-detail {
        background: #ffffff;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
      }

      .detail-header h2 {
        margin: 0 0 12px;
        font-size: 22px;
        font-weight: 700;
        color: #1a1a1a;
      }

      .meta {
        display: flex;
        align-items: center;
        gap: 20px;
        flex-wrap: wrap;
        margin-bottom: 20px;
        padding-bottom: 16px;
        border-bottom: 1px solid #e5e7eb;
      }

      .meta-item {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
        color: #6b7280;
      }

      .meta-item mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
      }

      .section-content {
        margin: 0;
        white-space: pre-wrap;
        font-family: inherit;
        color: #374151;
        line-height: 1.6;
      }

      .placeholder {
        flex-direction: column;
        justify-content: center;
        text-align: center;
        height: 100%;
      }

      .placeholder mat-icon {
        font-size: 64px;
        width: 64px;
        height: 64px;
        color: #d1d5db;
      }
    `,
  ],
})
export class DocSectionsComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly sectionsService = inject(DocSectionsService);

  /** Nested-tree children accessor for MatTree. */
  readonly childrenAccessor = (node: DocSection) => node.children ?? [];

  readonly sections = signal<DocSection[]>([]);
  readonly selectedSection = signal<DocSection | null>(null);
  readonly isLoading = signal(false);
  readonly documentTitle = signal("");

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );
  readonly documentId = computed(
    () => this.route.snapshot.paramMap.get("documentId") ?? "",
  );
  readonly selectedId = computed(
    () => this.selectedSection()?.sectionId ?? null,
  );

  ngOnInit(): void {
    const docId = this.documentId();
    if (docId) {
      this.loadSections(docId);
    }
  }

  hasChildren(node: DocSection): boolean {
    return !!node.children && node.children.length > 0;
  }

  selectSection(node: DocSection): void {
    this.selectedSection.set(node);
  }

  typeLabel(sectionType: string): string {
    const labels: Record<string, string> = {
      functional: "Funkcjonalna",
      non_functional: "Niefunkcjonalna",
      instruction: "Instrukcja",
      unclassified: "Niesklasyfikowana",
    };
    return labels[sectionType] ?? sectionType;
  }

  private loadSections(documentId: string): void {
    this.isLoading.set(true);

    this.sectionsService
      .getSections(documentId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          this.documentTitle.set(response.filename);
          this.sections.set(response.sections);
          this.isLoading.set(false);
        },
        error: (err) => {
          console.error("Failed to load document sections:", err);
          this.isLoading.set(false);
        },
      });
  }
}
