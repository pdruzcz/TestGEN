import { Component, computed, inject, input, signal } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatIconModule } from "@angular/material/icon";
import { MatButtonModule } from "@angular/material/button";
import {
  SbomFormat,
  SecurityFinding,
  SecurityScanService,
} from "../../services/security-scan.service";

/**
 * Story 4.4: lists vulnerable-dependency findings (package, version, CVE, fix)
 * and lets the user download the generated SBOM (CycloneDX / SPDX) for the scan.
 */
@Component({
  selector: "app-dependency-report",
  standalone: true,
  imports: [CommonModule, MatIconModule, MatButtonModule],
  templateUrl: "./dependency-report.component.html",
  styleUrls: ["./dependency-report.component.scss"],
})
export class DependencyReportComponent {
  private readonly service = inject(SecurityScanService);

  readonly projectId = input.required<string>();
  readonly scanId = input.required<string>();
  readonly findings = input.required<SecurityFinding[]>();

  readonly isDownloading = signal(false);
  readonly downloadError = signal<string | null>(null);

  readonly rows = computed(() =>
    this.findings().map((f) => ({
      severity: f.severity,
      package: (f.findingMetadata?.["package"] as string) ?? "—",
      version: (f.findingMetadata?.["version"] as string) ?? "—",
      cveId: (f.findingMetadata?.["cve_id"] as string) ?? "—",
      cvss: (f.findingMetadata?.["cvss_score"] as number) ?? null,
      fixedVersion: (f.findingMetadata?.["fixed_version"] as string) ?? null,
      recommendation: f.recommendation,
    })),
  );

  downloadSbom(sbomFormat: SbomFormat): void {
    if (this.isDownloading()) return;
    this.isDownloading.set(true);
    this.downloadError.set(null);
    this.service.getSbom(this.projectId(), this.scanId(), sbomFormat).subscribe({
      next: (sbom) => {
        this.saveJson(sbom, `sbom-${sbomFormat}-${this.scanId()}.json`);
        this.isDownloading.set(false);
      },
      error: () => {
        this.downloadError.set("Nie udało się pobrać SBOM.");
        this.isDownloading.set(false);
      },
    });
  }

  private saveJson(data: unknown, filename: string): void {
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }
}
