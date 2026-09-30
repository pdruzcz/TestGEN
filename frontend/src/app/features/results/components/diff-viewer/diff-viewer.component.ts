import { Component, computed, input } from "@angular/core";
import { CommonModule } from "@angular/common";
import { highlightLine } from "../code-highlighter/code-highlighter.component";

export type DiffLineType = "same" | "added" | "removed" | "empty";

export interface DiffRow {
  leftNo: number | null;
  leftHtml: string;
  leftType: DiffLineType;
  rightNo: number | null;
  rightHtml: string;
  rightType: DiffLineType;
}

/** Diff liniowy oparty o LCS — bez zewnętrznych bibliotek (brak jsdiff w deps). */
export function computeDiffRows(
  original: string,
  modified: string,
  language: string,
): DiffRow[] {
  const a = original.replace(/\r\n/g, "\n").split("\n");
  const b = modified.replace(/\r\n/g, "\n").split("\n");

  // LCS table (capped to keep O(n*m) reasonable for snippets).
  const n = Math.min(a.length, 500);
  const m = Math.min(b.length, 500);
  const lcs: number[][] = Array.from({ length: n + 1 }, () =>
    new Array(m + 1).fill(0),
  );
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[i][j] =
        a[i] === b[j]
          ? lcs[i + 1][j + 1] + 1
          : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
    }
  }

  const rows: DiffRow[] = [];
  let i = 0;
  let j = 0;
  const removed: number[] = [];
  const added: number[] = [];

  const flush = () => {
    const count = Math.max(removed.length, added.length);
    for (let k = 0; k < count; k++) {
      const li = removed[k];
      const ri = added[k];
      rows.push({
        leftNo: li !== undefined ? li + 1 : null,
        leftHtml: li !== undefined ? highlightLine(a[li], language) : "",
        leftType: li !== undefined ? "removed" : "empty",
        rightNo: ri !== undefined ? ri + 1 : null,
        rightHtml: ri !== undefined ? highlightLine(b[ri], language) : "",
        rightType: ri !== undefined ? "added" : "empty",
      });
    }
    removed.length = 0;
    added.length = 0;
  };

  while (i < n && j < m) {
    if (a[i] === b[j]) {
      flush();
      rows.push({
        leftNo: i + 1,
        leftHtml: highlightLine(a[i], language),
        leftType: "same",
        rightNo: j + 1,
        rightHtml: highlightLine(b[j], language),
        rightType: "same",
      });
      i++;
      j++;
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) {
      removed.push(i);
      i++;
    } else {
      added.push(j);
      j++;
    }
  }
  while (i < a.length) removed.push(i++);
  while (j < b.length) added.push(j++);
  flush();
  return rows;
}

/**
 * AC6 — widok diff side-by-side: oryginał (lewo) vs poprawka (prawo),
 * linie usunięte na czerwono, dodane na zielono, z numeracją linii.
 */
@Component({
  selector: "app-diff-viewer",
  standalone: true,
  imports: [CommonModule],
  templateUrl: "./diff-viewer.component.html",
  styleUrls: ["./diff-viewer.component.scss"],
})
export class DiffViewerComponent {
  readonly original = input<string>("");
  readonly modified = input<string>("");
  readonly language = input<string>("python");

  readonly rows = computed<DiffRow[]>(() =>
    computeDiffRows(
      this.original() ?? "",
      this.modified() ?? "",
      (this.language() || "python").toLowerCase(),
    ),
  );
}
