import {
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  signal,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatCardModule } from "@angular/material/card";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatSelectModule } from "@angular/material/select";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatTableModule } from "@angular/material/table";
import { NavbarComponent } from "../../../../../shared/components/navbar.component";
import { FooterComponent } from "../../../../../shared/components/footer.component";
import { TaintPathViewerComponent } from "../taint-path-viewer/taint-path-viewer.component";
import { DependencyReportComponent } from "../dependency-report/dependency-report.component";
import { ConfigReportComponent } from "../config-report/config-report.component";
import {
  DastConfigComponent,
  DastLaunchConfig,
} from "../dast-config/dast-config.component";
import { SecurityReportComponent } from "../security-report/security-report.component";
import { RiskDashboardComponent } from "../risk-dashboard/risk-dashboard.component";
import {
  ScanType,
  SecurityFinding,
  SecurityScanService,
  SecurityScanStatus,
} from "../../services/security-scan.service";
import {
  ConfigService,
  engineModeLabel,
} from "../../../../../core/services/config.service";

/**
 * Story 4.1: launches a security scan (SAST), lists the project's scans with
 * their per-severity breakdown, and shows the findings for a selected scan.
 */
@Component({
  selector: "app-scan-launcher",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    MatButtonModule,
    MatIconModule,
    MatCardModule,
    MatFormFieldModule,
    MatSelectModule,
    MatProgressSpinnerModule,
    MatTableModule,
    NavbarComponent,
    FooterComponent,
    TaintPathViewerComponent,
    DependencyReportComponent,
    ConfigReportComponent,
    DastConfigComponent,
    SecurityReportComponent,
    RiskDashboardComponent,
  ],
  templateUrl: "./scan-launcher.component.html",
  styleUrls: ["./scan-launcher.component.scss"],
})
export class ScanLauncherComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly service = inject(SecurityScanService);

  readonly projectId = signal("");
  readonly scans = signal<SecurityScanStatus[]>([]);
  readonly findings = signal<SecurityFinding[]>([]);
  readonly selectedScanId = signal<string | null>(null);
  readonly isLoading = signal(false);
  readonly isLaunching = signal(false);
  readonly errorMessage = signal<string | null>(null);

  /** Findings that carry a taint path — surfaced in the path viewer (Story 4.3). */
  readonly taintFindings = computed(() =>
    this.findings().filter((f) => f.taintPath),
  );

  /** Vulnerable-dependency findings — surfaced in the SCA report (Story 4.4). */
  readonly dependencyFindings = computed(() =>
    this.findings().filter((f) => f.scanType === "dependency"),
  );

  /** Infrastructure misconfigurations — surfaced in the config report (Story 4.5). */
  readonly configFindings = computed(() =>
    this.findings().filter((f) => f.scanType === "config"),
  );

  scanType: ScanType = "sast";
  private readonly configService = inject(ConfigService);
  readonly engineModeLabel = computed(() =>
    engineModeLabel(this.configService.configSignal().engineMode),
  );

  readonly displayedColumns = [
    "severity",
    "vulnerabilityType",
    "filePath",
    "line",
    "confidence",
  ];

  ngOnInit(): void {
    this.projectId.set(this.route.snapshot.paramMap.get("projectId") ?? "");
    this.loadScans();
  }

  loadScans(): void {
    if (!this.projectId()) return;
    this.isLoading.set(true);
    this.service
      .listScans(this.projectId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.scans.set(res.scans);
          this.isLoading.set(false);
        },
        error: () => {
          this.errorMessage.set("Nie udało się pobrać listy skanów.");
          this.isLoading.set(false);
        },
      });
  }

  launchScan(): void {
    if (!this.projectId() || this.isLaunching()) return;
    this.isLaunching.set(true);
    this.errorMessage.set(null);
    this.service
      .startScan(this.projectId(), {
        scanType: this.scanType,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.isLaunching.set(false);
          this.loadScans();
        },
        error: () => {
          this.errorMessage.set("Uruchomienie skanu nie powiodło się.");
          this.isLaunching.set(false);
        },
      });
  }

  launchDast(config: DastLaunchConfig): void {
    if (!this.projectId() || this.isLaunching()) return;
    this.isLaunching.set(true);
    this.errorMessage.set(null);
    this.service
      .startScan(this.projectId(), {
        scanType: "dast",
        targetUrl: config.targetUrl,
        authConfig: config.authConfig,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.isLaunching.set(false);
          this.loadScans();
        },
        error: () => {
          this.errorMessage.set("Uruchomienie skanu DAST nie powiodło się.");
          this.isLaunching.set(false);
        },
      });
  }

  selectScan(scanId: string): void {
    this.selectedScanId.set(scanId);
    this.service
      .listFindings(this.projectId(), { scanId })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => this.findings.set(res.findings),
        error: () => this.errorMessage.set("Nie udało się pobrać podatności."),
      });
  }

  statusLabel(status: string): string {
    const map: Record<string, string> = {
      pending: "Oczekuje",
      running: "W toku",
      completed: "Zakończony",
      failed: "Błąd",
    };
    return map[status] ?? status;
  }

  scanTypeLabel(type: string): string {
    const map: Record<string, string> = {
      sast: "Statyczny (SAST)",
      taint: "Taint analysis",
      dependency: "Zależności (CVE)",
      config: "Konfiguracja",
      dast: "Dynamiczny (DAST)",
    };
    return map[type] ?? type;
  }
}
