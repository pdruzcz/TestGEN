import { Component, inject } from "@angular/core";
import { MAT_DIALOG_DATA, MatDialogModule } from "@angular/material/dialog";
import { MatProgressBarModule } from "@angular/material/progress-bar";

export interface ExportProgressDialogData {
  formatLabel: string;
}

/**
 * Story 6.7 (AC1/AC7) — dialog postępu generowania eksportu; zamykany
 * automatycznie przez komponent zlecający po pobraniu pliku.
 */
@Component({
  selector: "app-export-progress-dialog",
  standalone: true,
  imports: [MatDialogModule, MatProgressBarModule],
  templateUrl: "./export-progress-dialog.component.html",
  styles: [
    `
      .dialog-body {
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding-bottom: 8px;
      }
      .hint {
        margin: 0;
        font-size: 12px;
        color: #757575;
      }
    `,
  ],
})
export class ExportProgressDialogComponent {
  readonly data = inject<ExportProgressDialogData>(MAT_DIALOG_DATA);
}
