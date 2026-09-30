import { Component, input } from "@angular/core";
import { DatePipe } from "@angular/common";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { ReportData, ReportType } from "../../services/report.service";
import { ExecutiveSummaryComponent } from "../executive-summary/executive-summary.component";
import { TechnicalDetailsComponent } from "../technical-details/technical-details.component";
import { ExportButtonsComponent } from "../export-buttons/export-buttons.component";

/**
 * AC8 (6.6) — podgląd raportu w formacie HTML; eksport w 6 formatach
 * (PDF/HTML/CSV/Excel/JSON/YAML) przez ExportButtonsComponent (Story 6.7)
 * + lokalny wydruk (print CSS).
 */
@Component({
  selector: "app-report-preview",
  standalone: true,
  imports: [
    DatePipe,
    MatButtonModule,
    MatIconModule,
    ExecutiveSummaryComponent,
    TechnicalDetailsComponent,
    ExportButtonsComponent,
  ],
  templateUrl: "./report-preview.component.html",
  styleUrls: ["./report-preview.component.scss"],
})
export class ReportPreviewComponent {
  readonly data = input.required<ReportData>();
  readonly reportType = input.required<ReportType>();

  printReport(): void {
    window.print();
  }
}
