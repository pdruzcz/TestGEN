import {
  Component,
  DestroyRef,
  computed,
  inject,
  input,
  signal,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import {
  PatchPreview,
  PatchResult,
  SecurityFinding,
  SecurityScanService,
} from "../../services/security-scan.service";
import {
  ConfigService,
  engineModeLabel,
} from "../../../../../core/services/config.service";

type DiffLine = { text: string; kind: "add" | "del" | "meta" | "context" };

/**
 * Story 4.11: patch preview. Generates a git-apply-ready unified-diff patch for a
 * finding, shows the before/after code and the diff (vulnerable lines red, fixed
 * green), then lets the user persist + download the .patch file.
 */
@Component({
  selector: "app-patch-preview",
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: "./patch-preview.component.html",
  styleUrls: ["./patch-preview.component.scss"],
})
export class PatchPreviewComponent {
  private readonly service = inject(SecurityScanService);
  private readonly destroyRef = inject(DestroyRef);

  readonly projectId = input.required<string>();
  readonly finding = input.required<SecurityFinding>();

  readonly preview = signal<PatchPreview | null>(null);
  readonly generated = signal<PatchResult | null>(null);
  private readonly configService = inject(ConfigService);
  readonly isLoading = signal(false);
  readonly errorMessage = signal<string | null>(null);
  readonly engineMode = computed(
    () => this.configService.configSignal().engineMode,
  );
  readonly engineModeLabel = computed(() => engineModeLabel(this.engineMode()));

  readonly diffLines = computed<DiffLine[]>(() => {
    const diff = this.preview()?.patchContent ?? "";
    if (!diff) return [];
    return diff
      .split("\n")
      .map((text) => ({ text, kind: this.classify(text) }));
  });

  private classify(line: string): DiffLine["kind"] {
    if (
      line.startsWith("+++") ||
      line.startsWith("---") ||
      line.startsWith("@@")
    ) {
      return "meta";
    }
    if (line.startsWith("+")) return "add";
    if (line.startsWith("-")) return "del";
    return "context";
  }

  loadPreview(): void {
    this.isLoading.set(true);
    this.errorMessage.set(null);
    this.generated.set(null);
    this.service
      .previewPatch(this.projectId(), this.finding().id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.preview.set(res);
          this.isLoading.set(false);
        },
        error: () => {
          this.errorMessage.set("Nie udało się wygenerować podglądu poprawki.");
          this.isLoading.set(false);
        },
      });
  }

  download(): void {
    this.errorMessage.set(null);
    this.service
      .generatePatch(this.projectId(), this.finding().id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.generated.set(res);
          this.saveFile(res.patchContent, res.patchFilename);
        },
        error: (err) => {
          this.errorMessage.set(
            err?.status === 422
              ? "Brak różnicy między kodem podatnym a naprawionym — patch nie został utworzony."
              : "Nie udało się pobrać pliku .patch.",
          );
        },
      });
  }

  private saveFile(content: string, filename: string): void {
    const blob = new Blob([content], { type: "text/x-patch" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  }
}
