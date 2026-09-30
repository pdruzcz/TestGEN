import { Component, DestroyRef, inject, input } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatButtonModule } from "@angular/material/button";
import { MatDialog, MatDialogModule } from "@angular/material/dialog";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatSnackBar, MatSnackBarModule } from "@angular/material/snack-bar";
import { ReportData, ReportType } from "../../services/report.service";
import {
  EXPORT_FORMAT_LABELS,
  ExportFormat,
  ExportService,
} from "../../services/export.service";
import { ExportProgressDialogComponent } from "../export-progress-dialog/export-progress-dialog.component";

interface ExportButton {
  format: ExportFormat;
  label: string;
  icon: string;
}

export const EXPORT_BUTTONS: ExportButton[] = [
  { format: "pdf", label: EXPORT_FORMAT_LABELS.pdf, icon: "picture_as_pdf" },
  { format: "html", label: EXPORT_FORMAT_LABELS.html, icon: "code" },
  { format: "csv", label: EXPORT_FORMAT_LABELS.csv, icon: "table_view" },
  { format: "xlsx", label: EXPORT_FORMAT_LABELS.xlsx, icon: "grid_on" },
  { format: "json", label: EXPORT_FORMAT_LABELS.json, icon: "data_object" },
  { format: "yaml", label: EXPORT_FORMAT_LABELS.yaml, icon: "notes" },
];

/**
 * Story 6.7 (AC1-AC6) — 6 przycisków eksportu z blokadą podczas
 * generowania i wskaźnikiem postępu per format.
 */
@Component({
  selector: "app-export-buttons",
  standalone: true,
  imports: [
    MatButtonModule,
    MatDialogModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
  ],
  templateUrl: "./export-buttons.component.html",
  styleUrls: ["./export-buttons.component.scss"],
})
export class ExportButtonsComponent {
  private readonly exportService = inject(ExportService);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);

  readonly projectId = input.required<string>();
  readonly data = input.required<ReportData>();
  readonly reportType = input.required<ReportType>();

  readonly buttons = EXPORT_BUTTONS;
  readonly activeFormat = this.exportService.activeFormatSignal;

  onExport(format: ExportFormat): void {
    if (this.activeFormat() !== null) return;

    const dialogRef = this.dialog.open(ExportProgressDialogComponent, {
      width: "420px",
      disableClose: true,
      data: { formatLabel: EXPORT_FORMAT_LABELS[format] },
    });

    this.exportService
      .exportReport(this.projectId(), format, this.reportType(), this.data())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (filename) => {
          dialogRef.close();
          this.snackBar.open(`Pobrano plik: ${filename}`, "OK", {
            duration: 5000,
          });
        },
        error: () => {
          dialogRef.close();
          this.snackBar.open(
            "Eksport nie powiódł się. Spróbuj ponownie.",
            "OK",
            { duration: 5000 },
          );
        },
      });
  }
}
