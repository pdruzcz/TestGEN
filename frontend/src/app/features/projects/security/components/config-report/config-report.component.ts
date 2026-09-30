import { Component, computed, input } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatIconModule } from "@angular/material/icon";
import {
  ConfigType,
  SecurityFinding,
} from "../../services/security-scan.service";

/**
 * Story 4.5: lists infrastructure misconfigurations (Docker / Kubernetes /
 * Terraform) grouped with a technology icon, severity badge, recommendation and
 * an example of the correct configuration (fix_example from finding_metadata).
 */
@Component({
  selector: "app-config-report",
  standalone: true,
  imports: [CommonModule, MatIconModule],
  templateUrl: "./config-report.component.html",
  styleUrls: ["./config-report.component.scss"],
})
export class ConfigReportComponent {
  readonly findings = input.required<SecurityFinding[]>();

  readonly rows = computed(() =>
    this.findings().map((f) => {
      const meta = f.findingMetadata ?? {};
      const configType = (meta["config_type"] as ConfigType) ?? "config";
      return {
        severity: f.severity,
        configType,
        icon: this.configIcon(configType),
        ruleId: (meta["rule_id"] as string) ?? "—",
        description: f.description,
        filePath: f.filePath,
        line: f.lineStart,
        recommendation: f.recommendation,
        fixExample: (meta["fix_example"] as string) ?? "",
      };
    }),
  );

  configIcon(type: ConfigType): string {
    const map: Record<ConfigType, string> = {
      docker: "directions_boat",
      kubernetes: "hub",
      terraform: "cloud",
      config: "settings",
    };
    return map[type] ?? "settings";
  }

  configLabel(type: ConfigType): string {
    const map: Record<ConfigType, string> = {
      docker: "Docker",
      kubernetes: "Kubernetes",
      terraform: "Terraform",
      config: "Konfiguracja",
    };
    return map[type] ?? type;
  }
}
