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
  BatchPatchResult,
  ConflictReport,
  PatchResult,
  SecurityScanService,
} from "../../services/security-scan.service";

type FileGroup = { filePath: string; patches: PatchResult[] };

/**
 * Story 4.11: security patches list. Generates one patch per finding for the
 * project, groups them per file, flags conflicting pairs and offers a batch
 * download ("Pobierz wszystkie") plus per-patch single download.
 */
@Component({
  selector: "app-patches-list",
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: "./patches-list.component.html",
  styleUrls: ["./patches-list.component.scss"],
})
export class PatchesListComponent {
  private readonly service = inject(SecurityScanService);
  private readonly destroyRef = inject(DestroyRef);

  readonly projectId = input.required<string>();

  readonly result = signal<BatchPatchResult | null>(null);
  readonly isLoading = signal(false);
  readonly errorMessage = signal<string | null>(null);

  readonly groups = computed<FileGroup[]>(() => {
    const patches = this.result()?.patches ?? [];
    const byFile = new Map<string, PatchResult[]>();
    for (const patch of patches) {
      const list = byFile.get(patch.filePath) ?? [];
      list.push(patch);
      byFile.set(patch.filePath, list);
    }
    return Array.from(byFile.entries()).map(([filePath, group]) => ({
      filePath,
      patches: group,
    }));
  });

  readonly conflicts = computed<ConflictReport[]>(
    () => this.result()?.conflicts ?? [],
  );

  generate(): void {
    this.isLoading.set(true);
    this.errorMessage.set(null);
    this.service
      .generateBatchPatches(this.projectId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.result.set(res);
          this.isLoading.set(false);
        },
        error: () => {
          this.errorMessage.set("Nie udało się wygenerować poprawek bezpieczeństwa.");
          this.isLoading.set(false);
        },
      });
  }

  conflictCount(patch: PatchResult): number {
    return patch.conflicts.length;
  }

  downloadAll(): void {
    for (const patch of this.result()?.patches ?? []) {
      if (patch.patchContent) {
        this.saveFile(patch.patchContent, patch.patchFilename);
      }
    }
  }

  download(patch: PatchResult): void {
    if (patch.patchContent) {
      this.saveFile(patch.patchContent, patch.patchFilename);
    }
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
