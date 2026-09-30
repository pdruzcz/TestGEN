import { Component, input } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatIconModule } from "@angular/material/icon";
import { TaintPath, TaintNodeType } from "../../services/security-scan.service";

/**
 * Story 4.3: renders a taint path as a linear graph
 * source (czerwony) → transformacje (żółty) → sink (kolor wagi). Each node shows
 * the file:line, variable, and the operation snippet.
 */
@Component({
  selector: "app-taint-path-viewer",
  standalone: true,
  imports: [CommonModule, MatIconModule],
  templateUrl: "./taint-path-viewer.component.html",
  styleUrls: ["./taint-path-viewer.component.scss"],
})
export class TaintPathViewerComponent {
  readonly taintPath = input.required<TaintPath>();

  nodeLabel(type: TaintNodeType): string {
    const map: Record<TaintNodeType, string> = {
      source: "Źródło danych",
      transform: "Przepływ",
      sanitizer: "Sanitizer",
      sink: "Ujście",
    };
    return map[type] ?? type;
  }

  nodeIcon(type: TaintNodeType): string {
    const map: Record<TaintNodeType, string> = {
      source: "input",
      transform: "arrow_forward",
      sanitizer: "cleaning_services",
      sink: "dangerous",
    };
    return map[type] ?? "circle";
  }
}
