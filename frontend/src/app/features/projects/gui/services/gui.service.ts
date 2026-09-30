import { Injectable, inject } from "@angular/core";
import { HttpClient, HttpParams, HttpEventType } from "@angular/common/http";
import { Observable, map } from "rxjs";
import { environment } from "../../../../../environments/environment";

/**
 * HTTP wrapper for Epic 3, Story 3.8 (GUI screenshot upload and analysis).
 *
 * Response payloads arrive after the global snakeCaseInterceptor has
 * transformed keys, so camelCase interfaces are declared client-side.
 */

export type GUIStatus = "pending" | "processing" | "completed" | "failed";

export type GUIComponentType =
  | "button"
  | "input"
  | "dropdown"
  | "checkbox"
  | "radio"
  | "menu"
  | "link"
  | "table"
  | "form"
  | "modal"
  | "tab"
  | "unknown";

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface GUIScreenshot {
  id: string;
  filename: string;
  status: GUIStatus;
  screenSequence: number;
  fileSize: number;
  createdAt: string | null;
}

export interface GUIUploadItem {
  screenshotId: string | null;
  filename: string;
  status: "accepted" | "rejected";
  taskId: string | null;
  rejectionReason: string | null;
}

export interface GUIUploadResponse {
  projectId: string;
  accepted: GUIUploadItem[];
  rejected: GUIUploadItem[];
  totalAccepted: number;
  totalRejected: number;
}

/**
 * Story 1.51-zakańczenie (Part A2): HTML/DOM GUI source upload response.
 * Each accepted HTML file becomes a DOM analysis whose components carry real
 * locator attributes (data-testid/aria-label/role) that feed self-healing.
 */
export interface DOMUploadItem {
  domSourceId: string | null;
  filename: string;
  status: "accepted" | "rejected";
  taskId: string | null;
  rejectionReason: string | null;
}

export interface DOMUploadResponse {
  projectId: string;
  accepted: DOMUploadItem[];
  rejected: DOMUploadItem[];
  a11yAccepted: boolean;
  totalAccepted: number;
  totalRejected: number;
}

export interface GUIAnalyzeTask {
  screenshotId: string | null;
  taskId: string | null;
  status: string;
}

export interface OCRTextBlock {
  text: string;
  bbox: BoundingBox;
  confidence: number;
}

export interface GUIComponentOut {
  id: string | null;
  componentType: GUIComponentType;
  label: string | null;
  bbox: BoundingBox | null;
  confidence: number;
  attributes: Record<string, unknown> | null;
}

export interface LayoutNode {
  type: string;
  label: string | null;
  bbox: BoundingBox | null;
  children: LayoutNode[];
}

export interface GUIAnalysisResponse {
  screenshotId: string;
  status: GUIStatus;
  ocrTextBlocks: OCRTextBlock[];
  components: GUIComponentOut[];
  layoutTree: LayoutNode | null;
  warnings: string[];
  processingTimeMs: number;
}

export type FlowEngineMode = "native" | "llm" | "hybrid";

export interface GUIFlowStep {
  sequence: number;
  action: string;
  actor: string | null;
  targetElement: string | null;
  expectedResult: string | null;
  sourceDiagramId: string | null;
  sourceScreenshotId: string | null;
  source: string;
}

export interface GUIUserFlow {
  id: string | null;
  name: string;
  sourceType: string;
  sourceIds: string[] | null;
  steps: GUIFlowStep[];
  status: string;
  warnings: string[] | null;
  createdAt: string | null;
}

export interface GUIFlowListResponse {
  flows: GUIUserFlow[];
  total: number;
}

export interface GUIFlowReconstructionTask {
  taskId: string | null;
  status: string;
}

export type ComparisonStatus = "match" | "minor_diff" | "major_diff" | "error";

export type ChangeType =
  | "layout_change"
  | "text_change"
  | "color_change"
  | "element_added"
  | "element_removed"
  | "element_moved";

export type ChangeSeverity = "breaking" | "visual" | "minor";

export type VisualTestFramework = "playwright" | "cypress";

export interface ComponentDelta {
  componentType: string;
  changeType: ChangeType;
  severity: ChangeSeverity;
  description: string;
  baselineBbox: BoundingBox | null;
  comparisonBbox: BoundingBox | null;
  confidence: number;
}

export interface VisualRegressionResponse {
  id: string | null;
  baselineScreenshotId: string;
  comparisonScreenshotId: string;
  pixelDiffPercentage: number;
  status: ComparisonStatus;
  semanticDiff: ComponentDelta[];
  diffImageUrl: string | null;
  testCode: string | null;
  warnings: string[];
  createdAt: string | null;
}

export interface VisualRegressionListItem {
  id: string;
  baselineScreenshotId: string;
  comparisonScreenshotId: string;
  pixelDiffPercentage: number;
  status: ComparisonStatus;
  createdAt: string | null;
}

export interface VisualRegressionListResponse {
  items: VisualRegressionListItem[];
  total: number;
  page: number;
  pageSize: number;
}

@Injectable({ providedIn: "root" })
export class GuiService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  /** Upload GUI screenshots. Returns 202 with accepted/rejected breakdown + task ids. */
  uploadScreenshots(
    projectId: string,
    files: File[],
    onProgress?: (progress: number) => void,
  ): Observable<GUIUploadResponse> {
    const formData = new FormData();
    for (const file of files) {
      formData.append("files", file, file.name);
    }

    return this.http
      .post<GUIUploadResponse>(
        `${this.apiUrl}/projects/${projectId}/gui/upload`,
        formData,
        {
          reportProgress: true,
          observe: "events",
        },
      )
      .pipe(
        map((event) => {
          if (event.type === HttpEventType.UploadProgress && onProgress) {
            const progress = event.total
              ? Math.round((event.loaded / event.total) * 100)
              : 0;
            onProgress(progress);
          } else if (event.type === HttpEventType.Response) {
            return event.body as GUIUploadResponse;
          }
          return null as unknown as GUIUploadResponse;
        }),
      ) as Observable<GUIUploadResponse>;
  }

  /**
   * Upload HTML/DOM as a GUI source (sibling of screenshots) — Story
   * 1.51-zakańczenie (Part A2). Origin-based routing: HTML here is analysed as
   * GUI structure; HTML routed as documentation still goes to the E2 parser.
   * `a11yFile` is an optional axe-core JSON dump; `versionLabel` tags the run
   * for before/after healing selection.
   */
  uploadDomSources(
    projectId: string,
    htmlFiles: File[],
    a11yFile?: File | null,
    versionLabel?: string,
  ): Observable<DOMUploadResponse> {
    const formData = new FormData();
    for (const file of htmlFiles) {
      formData.append("files", file, file.name);
    }
    if (a11yFile) {
      formData.append("a11y", a11yFile, a11yFile.name);
    }
    if (versionLabel) {
      formData.append("version_label", versionLabel);
    }
    return this.http.post<DOMUploadResponse>(
      `${this.apiUrl}/projects/${projectId}/gui/dom/upload`,
      formData,
    );
  }

  /** Paginated list of a project's GUI screenshots. */
  listScreenshots(
    projectId: string,
    page = 1,
    pageSize = 20,
  ): Observable<{ screenshots: GUIScreenshot[]; total: number }> {
    const params = new HttpParams()
      .set("page", String(page))
      .set("page_size", String(pageSize));

    return this.http.get<{ screenshots: GUIScreenshot[]; total: number }>(
      `${this.apiUrl}/projects/${projectId}/gui`,
      {
        params,
      },
    );
  }

  /** Force (re)analysis of a specific screenshot. Returns 202 + task id. */
  analyzeScreenshot(
    projectId: string,
    screenshotId: string,
  ): Observable<GUIAnalyzeTask> {
    return this.http.post<GUIAnalyzeTask>(
      `${this.apiUrl}/projects/${projectId}/gui/analyze`,
      {
        screenshot_id: screenshotId,
      },
    );
  }

  /** Screenshot analysis result: OCR text blocks, components and layout tree. */
  getResult(
    projectId: string,
    screenshotId: string,
  ): Observable<GUIAnalysisResponse> {
    return this.http.get<GUIAnalysisResponse>(
      `${this.apiUrl}/projects/${projectId}/gui/${screenshotId}/result`,
    );
  }

  /** Dispatch reconstruction of a GUI user flow from a screenshot sequence (Story 3.9). */
  reconstructFlows(
    projectId: string,
    screenshotIds: string[] | null,
  ): Observable<GUIFlowReconstructionTask> {
    return this.http.post<GUIFlowReconstructionTask>(
      `${this.apiUrl}/projects/${projectId}/gui/flows`,
      {
        screenshot_ids: screenshotIds,
      },
    );
  }

  /** Paginated list of GUI-reconstructed user flows for a project (Story 3.9). */
  listFlows(
    projectId: string,
    page = 1,
    pageSize = 20,
  ): Observable<GUIFlowListResponse> {
    const params = new HttpParams()
      .set("page", String(page))
      .set("page_size", String(pageSize));

    return this.http.get<GUIFlowListResponse>(
      `${this.apiUrl}/projects/${projectId}/gui/flows`,
      { params },
    );
  }

  /** Compare two screenshots synchronously (Story 3.10). */
  compareScreenshots(
    projectId: string,
    baselineScreenshotId: string,
    comparisonScreenshotId: string,
    pixelThreshold = 0.02,
    generateTestCode = false,
    testFramework: VisualTestFramework = "playwright",
  ): Observable<VisualRegressionResponse> {
    return this.http.post<VisualRegressionResponse>(
      `${this.apiUrl}/projects/${projectId}/gui/compare`,
      {
        baseline_screenshot_id: baselineScreenshotId,
        comparison_screenshot_id: comparisonScreenshotId,
        pixel_threshold: pixelThreshold,
        generate_test_code: generateTestCode,
        test_framework: testFramework,
      },
    );
  }

  /** Paginated list of stored visual-regression comparisons (Story 3.10). */
  listComparisons(
    projectId: string,
    page = 1,
    pageSize = 20,
  ): Observable<VisualRegressionListResponse> {
    const params = new HttpParams()
      .set("page", String(page))
      .set("page_size", String(pageSize));

    return this.http.get<VisualRegressionListResponse>(
      `${this.apiUrl}/projects/${projectId}/gui/comparisons`,
      {
        params,
      },
    );
  }

  /** Absolute URL to a comparison's annotated diff-image. */
  diffImageUrl(projectId: string, comparisonId: string): string {
    return `${this.apiUrl}/projects/${projectId}/gui/comparisons/${comparisonId}/diff`;
  }
}
