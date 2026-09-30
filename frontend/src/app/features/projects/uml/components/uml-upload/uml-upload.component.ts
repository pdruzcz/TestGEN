import { Component, inject, signal, computed, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { RouterLink, ActivatedRoute } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { DestroyRef } from "@angular/core";
import { NavbarComponent } from "../../../../../shared/components/navbar.component";
import { FooterComponent } from "../../../../../shared/components/footer.component";
import { UmlService, UMLDiagram } from "../../services/uml.service";

// Keep in sync with backend/app/services/analysis/uml/upload_service.py
const UML_EXTENSIONS: ReadonlyArray<string> = [
  // Tier 1 — semantic/textual (Story 3.1).
  ".xmi",
  ".xml",
  ".puml",
  ".plantuml",
  // Tier 2 — visual (Story 3.1b): SVG, PDF, raster images.
  ".svg",
  ".pdf",
  ".png",
  ".jpeg",
  ".jpg",
];

const MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024; // 100MB Basic / 500MB Professional

function extensionOf(filename: string): string {
  const lower = filename.toLowerCase();
  const idx = lower.lastIndexOf(".");
  return idx === -1 ? "" : lower.slice(idx);
}

function isUmlExtension(filename: string): boolean {
  return UML_EXTENSIONS.includes(extensionOf(filename));
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  return `${mb.toFixed(1)} MB`;
}

interface UploadedDiagram extends UMLDiagram {
  uiStatus: "pending" | "parsing" | "completed" | "failed";
}

@Component({
  selector: "app-uml-upload",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    RouterLink,
    NavbarComponent,
    FooterComponent,
  ],
  templateUrl: "./uml-upload.component.html",
  styleUrls: ["./uml-upload.component.scss"],
})
export class UmlUploadComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly umlService = inject(UmlService);

  readonly diagrams = signal<UploadedDiagram[]>([]);
  readonly isLoadingList = signal(false);
  readonly isDragActive = signal(false);
  readonly isUploading = signal(false);
  readonly isAnalyzing = signal(false);
  readonly uploadError = signal("");
  readonly uploadSummary = signal("");
  readonly analyzeSummary = signal("");

  readonly hasParsedDiagrams = computed(() =>
    this.diagrams().some((d) => d.status === "completed"),
  );

  readonly allowedExtensionsLabel =
    "XMI, PlantUML, SVG, PDF, obrazy PNG/JPEG (" +
    UML_EXTENSIONS.join(", ") +
    ")";
  readonly maxFileSizeLabel = formatBytes(MAX_FILE_SIZE_BYTES);

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  ngOnInit(): void {
    if (this.projectId()) {
      this.loadDiagrams();
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
    }
    input.value = "";
  }

  private handleFiles(selected: File[]): void {
    this.uploadError.set("");
    this.uploadSummary.set("");

    const accepted: File[] = [];
    for (const file of selected) {
      if (!isUmlExtension(file.name)) {
        this.uploadError.set(
          `Nieobsługiwany format: ${extensionOf(file.name)}. Akceptowane: ${this.allowedExtensionsLabel}`,
        );
        return;
      }
      if (file.size > MAX_FILE_SIZE_BYTES) {
        this.uploadError.set(
          `Plik przekracza limit ${this.maxFileSizeLabel}. ${file.name} ma ${formatBytes(file.size)}.`,
        );
        return;
      }
      accepted.push(file);
    }

    if (accepted.length === 0) return;
    this.isUploading.set(true);

    this.umlService
      .uploadUml(this.projectId(), accepted)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          if (!response) return;
          this.isUploading.set(false);
          this.uploadSummary.set(
            `Przesłano ${response.totalAccepted} diagramów. Rozpoczęto parsowanie…`,
          );
          if (response.totalRejected > 0) {
            this.uploadError.set(`Odrzucono ${response.totalRejected} plików.`);
          }
          this.loadDiagrams();
        },
        error: (err) => {
          this.isUploading.set(false);
          this.uploadError.set(
            `Błąd wysyłania: ${err?.error?.detail || err?.message || "Nieznany błąd"}`,
          );
        },
      });
  }

  private loadDiagrams(): void {
    this.isLoadingList.set(true);
    this.umlService
      .listDiagrams(this.projectId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ({ diagrams }) => {
          this.diagrams.set(
            diagrams.map((d) => ({ ...d, uiStatus: d.status })),
          );
          this.isLoadingList.set(false);
        },
        error: () => {
          this.uploadError.set("Błąd ładowania diagramów");
          this.isLoadingList.set(false);
        },
      });
  }

  /** Launch cross-diagram analysis to reconstruct user flows (Story 3.7). */
  analyzeFlows(): void {
    this.analyzeSummary.set("");
    this.uploadError.set("");
    this.isAnalyzing.set(true);
    this.umlService
      .analyzeFlows(this.projectId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.isAnalyzing.set(false);
          this.analyzeSummary.set(
            "Rozpoczęto analizę cross-diagram. User flows pojawią się po zakończeniu.",
          );
        },
        error: (err) => {
          this.isAnalyzing.set(false);
          this.uploadError.set(
            `Błąd analizy: ${err?.error?.detail || err?.message || "Nieznany błąd"}`,
          );
        },
      });
  }

  getDiagramIcon(d: UploadedDiagram): string {
    switch (d.format) {
      case "xmi":
        return "account_tree";
      case "plantuml":
        return "schema";
      case "pdf":
        return "picture_as_pdf";
      case "svg":
      case "raster":
        return "image";
      default:
        return "schema";
    }
  }

  /** Route to the type-specific viewer, or null when no viewer exists yet. */
  viewerLink(d: UploadedDiagram): unknown[] | null {
    const viewerByType: Record<string, string> = {
      sequence: "sequence",
      use_case: "usecase",
      class: "class",
      activity: "activity",
      state_machine: "state",
    };
    const segment = d.diagramType ? viewerByType[d.diagramType] : undefined;
    if (!segment) return null;
    return ["/projects", this.projectId(), "uml", segment, d.id];
  }

  getTypeLabel(t: string | null): string {
    const map: Record<string, string> = {
      sequence: "Sekwencji",
      use_case: "Przypadków użycia",
      class: "Klas",
      activity: "Aktywności",
      state_machine: "Stanów",
    };
    return t ? (map[t] ?? t) : "—";
  }

  formatSize(size: number): string {
    return formatBytes(size);
  }
}
