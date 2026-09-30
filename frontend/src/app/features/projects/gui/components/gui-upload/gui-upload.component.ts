import {
  Component,
  inject,
  signal,
  computed,
  OnInit,
  DestroyRef,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { RouterLink, ActivatedRoute } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { NavbarComponent } from "../../../../../shared/components/navbar.component";
import { FooterComponent } from "../../../../../shared/components/footer.component";
import { GuiService, GUIScreenshot } from "../../services/gui.service";

// Keep in sync with backend/app/services/analysis/gui/upload_service.py
const GUI_EXTENSIONS: ReadonlyArray<string> = [
  ".png",
  ".jpg",
  ".jpeg",
  ".bmp",
  ".tif",
  ".tiff",
  ".webp",
];

// Keep in sync with backend dom_upload_service.DOM_ALLOWED_EXTENSIONS (Story 1.51)
const DOM_EXTENSIONS: ReadonlyArray<string> = [".html", ".htm"];

const MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024; // 20MB

function extensionOf(filename: string): string {
  const lower = filename.toLowerCase();
  const idx = lower.lastIndexOf(".");
  return idx === -1 ? "" : lower.slice(idx);
}

function isGuiExtension(filename: string): boolean {
  return GUI_EXTENSIONS.includes(extensionOf(filename));
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  return `${mb.toFixed(1)} MB`;
}

@Component({
  selector: "app-gui-upload",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule,
    RouterLink,
    NavbarComponent,
    FooterComponent,
  ],
  templateUrl: "./gui-upload.component.html",
  styleUrls: ["./gui-upload.component.scss"],
})
export class GuiUploadComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly guiService = inject(GuiService);

  readonly screenshots = signal<GUIScreenshot[]>([]);
  readonly isLoadingList = signal(false);
  readonly isDragActive = signal(false);
  readonly isUploading = signal(false);
  readonly uploadError = signal("");
  readonly uploadSummary = signal("");

  // Story 1.51-zakańczenie (Part A2): HTML/DOM GUI source upload.
  readonly domVersionLabel = signal("");
  readonly domUploading = signal(false);
  readonly domError = signal("");
  readonly domSummary = signal("");

  readonly allowedExtensionsLabel =
    "PNG, JPEG, BMP, TIFF, WebP (" + GUI_EXTENSIONS.join(", ") + ")";
  readonly maxFileSizeLabel = formatBytes(MAX_FILE_SIZE_BYTES);
  readonly domExtensionsLabel = "HTML (" + DOM_EXTENSIONS.join(", ") + ")";

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  ngOnInit(): void {
    if (this.projectId()) {
      this.loadScreenshots();
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
      if (!isGuiExtension(file.name)) {
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

    this.guiService
      .uploadScreenshots(this.projectId(), accepted)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          if (!response) return;
          this.isUploading.set(false);
          this.uploadSummary.set(
            `Przesłano ${response.totalAccepted} zrzutów. Rozpoczęto analizę…`,
          );
          if (response.totalRejected > 0) {
            this.uploadError.set(`Odrzucono ${response.totalRejected} plików.`);
          }
          this.loadScreenshots();
        },
        error: (err) => {
          this.isUploading.set(false);
          this.uploadError.set(
            `Błąd wysyłania: ${err?.error?.detail || err?.message || "Nieznany błąd"}`,
          );
        },
      });
  }

  private loadScreenshots(): void {
    this.isLoadingList.set(true);
    this.guiService
      .listScreenshots(this.projectId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ({ screenshots }) => {
          this.screenshots.set(screenshots);
          this.isLoadingList.set(false);
        },
        error: () => {
          this.uploadError.set("Błąd ładowania zrzutów ekranu");
          this.isLoadingList.set(false);
        },
      });
  }

  /**
   * Story 1.51-zakańczenie (Part A2): select HTML/DOM files to upload as a GUI
   * source. Feeds self-healing with real locator attributes.
   */
  onDomFilesSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const files = input.files ? Array.from(input.files) : [];
    input.value = "";
    if (files.length > 0) this.uploadDom(files);
  }

  private uploadDom(files: File[]): void {
    this.domError.set("");
    this.domSummary.set("");

    const accepted: File[] = [];
    for (const file of files) {
      if (!DOM_EXTENSIONS.includes(extensionOf(file.name))) {
        this.domError.set(
          `Nieobsługiwany format: ${extensionOf(file.name)}. Akceptowane: ${this.domExtensionsLabel}`,
        );
        return;
      }
      if (file.size > MAX_FILE_SIZE_BYTES) {
        this.domError.set(
          `Plik przekracza limit ${this.maxFileSizeLabel}. ${file.name} ma ${formatBytes(file.size)}.`,
        );
        return;
      }
      accepted.push(file);
    }
    if (accepted.length === 0) return;

    this.domUploading.set(true);
    this.guiService
      .uploadDomSources(
        this.projectId(),
        accepted,
        null,
        this.domVersionLabel().trim() || undefined,
      )
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          this.domUploading.set(false);
          this.domSummary.set(
            `Przesłano ${response.totalAccepted} źródeł HTML/DOM. Rozpoczęto analizę lokatorów…`,
          );
          if (response.totalRejected > 0) {
            this.domError.set(`Odrzucono ${response.totalRejected} plików.`);
          }
          this.domVersionLabel.set("");
        },
        error: (err) => {
          this.domUploading.set(false);
          this.domError.set(
            `Błąd wysyłania: ${err?.error?.detail || err?.message || "Nieznany błąd"}`,
          );
        },
      });
  }

  /** Re-run analysis for a screenshot. */
  reanalyze(screenshot: GUIScreenshot): void {
    this.guiService
      .analyzeScreenshot(this.projectId(), screenshot.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.uploadSummary.set(
            `Ponowna analiza ${screenshot.filename} rozpoczęta.`,
          );
          this.loadScreenshots();
        },
        error: (err) => {
          this.uploadError.set(
            `Błąd analizy: ${err?.error?.detail || err?.message || "Nieznany błąd"}`,
          );
        },
      });
  }

  resultLink(screenshot: GUIScreenshot): unknown[] {
    return ["/projects", this.projectId(), "gui", screenshot.id, "result"];
  }

  statusLabel(status: string): string {
    const map: Record<string, string> = {
      pending: "Oczekuje",
      processing: "Przetwarzanie",
      completed: "Ukończono",
      failed: "Błąd",
    };
    return map[status] ?? status;
  }

  formatSize(size: number): string {
    return formatBytes(size);
  }
}
