import { Component, DestroyRef, computed, inject } from "@angular/core";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { MatRadioModule } from "@angular/material/radio";
import { NavbarComponent } from "../../shared/components/navbar.component";
import { FooterComponent } from "../../shared/components/footer.component";
import {
  REPORT_STAGES,
  ReportService,
  ReportType,
} from "./services/report.service";
import { ReportPreviewComponent } from "./components/report-preview/report-preview.component";

/**
 * Story 6.6 — generator raportów (AC1 wybór typu, AC7 pasek postępu
 * z etapami, AC8 podgląd HTML z opcjami eksportu).
 */
@Component({
  selector: "app-reports",
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    MatButtonModule,
    MatIconModule,
    MatProgressBarModule,
    MatRadioModule,
    NavbarComponent,
    FooterComponent,
    ReportPreviewComponent,
  ],
  templateUrl: "./reports.component.html",
  styleUrls: ["./reports.component.scss"],
})
export class ReportsComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly reportService = inject(ReportService);

  readonly stages = REPORT_STAGES;

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  selectedType: ReportType = "executive";

  readonly status = this.reportService.reportStatusSignal;
  readonly stage = this.reportService.reportStageSignal;
  readonly reportData = this.reportService.reportDataSignal;
  readonly reportType = this.reportService.reportTypeSignal;

  readonly progressValue = computed(
    () => ((this.stage() + 1) / REPORT_STAGES.length) * 100,
  );

  constructor() {
    this.reportService.reset();
  }

  generate(): void {
    this.reportService
      .generateReport(this.projectId(), this.selectedType)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({ error: () => undefined });
  }
}
