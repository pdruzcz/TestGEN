import { Component, computed, input, signal } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatIconModule } from "@angular/material/icon";
import {
  FindingStatus,
  ScanType,
  SecurityFinding,
  Severity,
} from "../../services/security-scan.service";
import { FindingDetailComponent } from "../finding-detail/finding-detail.component";
import { PatchPreviewComponent } from "../patch-preview/patch-preview.component";
import { PocViewerComponent } from "../poc-viewer/poc-viewer.component";

/**
 * Story 4.7: renders aggregated findings with client-side filters (severity,
 * scan source, status, CWE, free-text vulnerability type / file) and surfaces
 * the contributing scan sources, confidence and a status-change action.
 *
 * Story 4.9: each row can expand to an inline recommendation view
 * (problem/risk/fix/diff) via the finding-detail component.
 *
 * Story 4.10: the expanded row also exposes a proof-of-concept viewer
 * (poc-viewer) for injection-class findings.
 *
 * Story 4.11: the expanded row also exposes a patch preview (patch-preview)
 * for findings with a known code location.
 */
@Component({
  selector: "app-findings-list",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatIconModule,
    FindingDetailComponent,
    PatchPreviewComponent,
    PocViewerComponent,
  ],
  templateUrl: "./findings-list.component.html",
  styleUrls: ["./findings-list.component.scss"],
})
export class FindingsListComponent {
  private static readonly POC_TYPES = new Set([
    "sql_injection",
    "xss",
    "command_injection",
    "path_traversal",
  ]);

  readonly findings = input.required<SecurityFinding[]>();
  readonly projectId = input<string | null>(null);

  readonly selectedFindingId = signal<string | null>(null);

  toggleDetail(findingId: string): void {
    this.selectedFindingId.update((id) => (id === findingId ? null : findingId));
  }

  supportsPoc(finding: SecurityFinding): boolean {
    return FindingsListComponent.POC_TYPES.has(finding.vulnerabilityType);
  }

  supportsPatch(finding: SecurityFinding): boolean {
    return Boolean(finding.filePath && finding.lineStart);
  }

  readonly severityFilter = signal<Severity | "">("");
  readonly sourceFilter = signal<ScanType | "">("");
  readonly statusFilter = signal<FindingStatus | "">("");
  readonly textFilter = signal("");

  readonly filtered = computed(() => {
    const sev = this.severityFilter();
    const src = this.sourceFilter();
    const status = this.statusFilter();
    const text = this.textFilter().toLowerCase().trim();
    return this.findings().filter((f) => {
      if (sev && f.severity !== sev) return false;
      if (src && f.scanType !== src) return false;
      if (status && f.status !== status) return false;
      if (text) {
        const hay = `${f.vulnerabilityType} ${f.filePath ?? ""} ${
          f.cweId ?? ""
        }`.toLowerCase();
        if (!hay.includes(text)) return false;
      }
      return true;
    });
  });

  sources(finding: SecurityFinding): string[] {
    const meta = finding.findingMetadata ?? {};
    const list = meta["sources"];
    return Array.isArray(list) ? (list as string[]) : [finding.scanType];
  }

  sourceIcon(source: string): string {
    const map: Record<string, string> = {
      sast: "code",
      taint: "alt_route",
      dependency: "inventory_2",
      config: "settings",
      dast: "travel_explore",
    };
    return map[source] ?? "bug_report";
  }
}
