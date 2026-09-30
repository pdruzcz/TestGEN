import { Component, DestroyRef, computed, inject, signal } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatButtonModule } from "@angular/material/button";
import {
  MAT_DIALOG_DATA,
  MatDialogModule,
  MatDialogRef,
} from "@angular/material/dialog";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatRadioModule } from "@angular/material/radio";
import { MatSnackBar, MatSnackBarModule } from "@angular/material/snack-bar";
import { FieldMappingComponent } from "../field-mapping/field-mapping.component";
import {
  FieldMapping,
  TMS_FORMAT_LABELS,
  TmsExportService,
  TmsFormat,
} from "../../services/tms-export.service";

export interface TmsExportDialogData {
  projectId: string;
  totalCount: number;
  filteredIds: string[];
  selectedIds: string[];
}

type ExportScope = "selected" | "filtered" | "all";

/**
 * Story 6.8, AC1/AC6/AC7 — dialog eksportu test case'ów do TMS:
 * wybór formatu (TestRail CSV / Jira Xray XML / Ogólny JSON), zakresu
 * (zaznaczone / przefiltrowane / wszystkie) i mapowania pól.
 */
@Component({
  selector: "app-tms-export-dialog",
  standalone: true,
  imports: [
    MatButtonModule,
    MatDialogModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatRadioModule,
    MatSnackBarModule,
    FieldMappingComponent,
  ],
  templateUrl: "./tms-export-dialog.component.html",
  styleUrls: ["./tms-export-dialog.component.scss"],
})
export class TmsExportDialogComponent {
  private readonly dialogRef =
    inject<MatDialogRef<TmsExportDialogComponent>>(MatDialogRef);
  private readonly destroyRef = inject(DestroyRef);
  private readonly snackBar = inject(MatSnackBar);
  private readonly exportService = inject(TmsExportService);

  readonly data = inject<TmsExportDialogData>(MAT_DIALOG_DATA);

  readonly formatLabels = TMS_FORMAT_LABELS;
  readonly formats: TmsFormat[] = ["testrail", "xray", "json"];

  readonly format = signal<TmsFormat>("testrail");
  readonly scope = signal<ExportScope>(
    this.data.selectedIds.length > 0 ? "selected" : "filtered",
  );
  readonly showMapping = signal(false);
  readonly mapping = signal<FieldMapping>(
    this.exportService.loadMapping("testrail"),
  );

  readonly isExporting = this.exportService.isExportingSignal;

  /** AC6 — liczba test case'ów objętych eksportem w wybranym zakresie. */
  readonly exportCount = computed(() => {
    switch (this.scope()) {
      case "selected":
        return this.data.selectedIds.length;
      case "filtered":
        return this.data.filteredIds.length;
      default:
        return this.data.totalCount;
    }
  });

  onFormatChange(format: TmsFormat): void {
    this.format.set(format);
    this.mapping.set(this.exportService.loadMapping(format));
  }

  onScopeChange(scope: ExportScope): void {
    this.scope.set(scope);
  }

  onMappingChange(mapping: FieldMapping): void {
    this.mapping.set(mapping);
  }

  toggleMapping(): void {
    this.showMapping.update((v) => !v);
  }

  export(): void {
    if (this.isExporting() || this.exportCount() === 0) return;
    const ids =
      this.scope() === "selected"
        ? this.data.selectedIds
        : this.scope() === "filtered"
          ? this.data.filteredIds
          : [];
    this.exportService
      .exportToTms(this.data.projectId, ids, this.format(), this.mapping())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (filename) => {
          this.snackBar.open(`Pobrano plik: ${filename}`, "OK", {
            duration: 4000,
          });
          this.dialogRef.close(true);
        },
        error: () =>
          this.snackBar.open(
            "Eksport do TMS nie powiódł się. Spróbuj ponownie.",
            "OK",
            { duration: 5000 },
          ),
      });
  }
}
