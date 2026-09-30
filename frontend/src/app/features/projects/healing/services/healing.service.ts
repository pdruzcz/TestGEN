import { Injectable, inject } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { Observable } from "rxjs";

import { environment } from "../../../../../environments/environment";

/**
 * HTTP wrapper for self-healing of UI test locators — Epic 1, Story 1.51 (FR69).
 *
 * Response keys arrive camelCased via the global snakeCaseInterceptor.
 * Request body for `heal` uses snake_case keys to match the backend
 * `HealRequest` (`version_a` / `version_b`).
 */
export interface HealTrigger {
  taskId: string;
  reportId: string;
  status: string;
}

export interface HealingItem {
  id: string;
  reportId: string;
  testCodeId: string;
  oldLocator: string;
  oldStrategy: string;
  newLocator: string | null;
  newStrategy: string | null;
  confidence: number;
  healingMethod: string;
  status: string;
  diffPreview: string | null;
  createdAt: string;
}

export interface HealingReport {
  id: string;
  projectId: string;
  versionA: string;
  versionB: string;
  status: string;
  stats: Record<string, number> | null;
  createdAt: string;
  items: HealingItem[];
}

export interface HealingDecision {
  itemId: string;
  status: string;
  applied: boolean;
}

/**
 * One row of the GUI analysis history — Story 1.51-zakańczenie (Part B1).
 * Powers the healing launcher's before/after version selectors. `sourceType` is
 * "dom" (HTML/DOM source, real locator attributes) or "screenshot".
 */
export interface GuiAnalysisOption {
  id: string;
  sourceType: string;
  createdAt: string | null;
  versionLabel: string | null;
  sourceLabel: string | null;
  screenSequence: number | null;
  componentCount: number;
}

export interface GuiAnalysisList {
  analyses: GuiAnalysisOption[];
  total: number;
  page: number;
  pageSize: number;
}

export type HealingAction = "accept" | "reject";

@Injectable({ providedIn: "root" })
export class HealingService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  /** Launch an async healing run between two GUI versions. Returns 202 + ids. */
  heal(
    projectId: string,
    versionA: string,
    versionB: string,
  ): Observable<HealTrigger> {
    return this.http.post<HealTrigger>(
      `${this.apiUrl}/projects/${projectId}/tests/heal`,
      {
        version_a: versionA,
        version_b: versionB,
      },
    );
  }

  /**
   * GUI analysis history (screenshot + DOM) for the launcher's version selectors
   * — Story 1.51-zakańczenie (Part B1). Replaces the old free-text analysis-id
   * inputs with a dropdown sourced from real analyses.
   */
  getGuiAnalyses(projectId: string): Observable<GuiAnalysisList> {
    return this.http.get<GuiAnalysisList>(
      `${this.apiUrl}/projects/${projectId}/gui/analyses`,
    );
  }

  /** Fetch a healing report with its items (status, confidence, diff). */
  getReport(projectId: string, reportId: string): Observable<HealingReport> {
    return this.http.get<HealingReport>(
      `${this.apiUrl}/projects/${projectId}/healing/${reportId}`,
    );
  }

  /** Accept (apply to TestCode) or reject a proposed locator fix. */
  decide(
    projectId: string,
    reportId: string,
    itemId: string,
    action: HealingAction,
  ): Observable<HealingDecision> {
    return this.http.post<HealingDecision>(
      `${this.apiUrl}/projects/${projectId}/healing/${reportId}/items/${itemId}/decision`,
      { action },
    );
  }
}
