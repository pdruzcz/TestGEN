import { Injectable, inject } from "@angular/core";
import { HttpClient, HttpParams, HttpEventType } from "@angular/common/http";
import { Observable, map } from "rxjs";
import { environment } from "../../../../../environments/environment";

/**
 * HTTP wrapper for Epic 3 (UML diagram upload and parsing).
 *
 * Response payloads arrive after the global snakeCaseInterceptor has
 * transformed keys, so camelCase interfaces are declared client-side.
 */

export type UMLFormat = "xmi" | "plantuml" | "svg" | "pdf" | "raster";
export type DiagramType =
  | "sequence"
  | "use_case"
  | "class"
  | "activity"
  | "state_machine";
export type UMLStatus = "pending" | "parsing" | "completed" | "failed";

export interface UMLDiagram {
  id: string;
  projectId: string;
  filename: string;
  format: UMLFormat;
  diagramType: DiagramType | null;
  status: UMLStatus;
  fileSize: number;
  createdAt: string;
}

export interface UMLUploadItem {
  diagramId: string | null;
  filename: string;
  format: UMLFormat | null;
  status: "accepted" | "rejected";
  taskId: string | null;
  rejectionReason: string | null;
}

export interface UMLUploadResponse {
  projectId: string;
  accepted: UMLUploadItem[];
  rejected: UMLUploadItem[];
  totalAccepted: number;
  totalRejected: number;
}

export interface SequenceParticipant {
  name: string;
  alias: string | null;
  participantType: string;
}

export interface SequenceMessage {
  fromAlias: string;
  toAlias: string;
  label: string;
  messageType: string;
  sequenceNumber: number;
}

export interface SequenceFragmentCondition {
  label: string;
  messageIndices: number[];
}

export interface SequenceFragment {
  fragmentType: string;
  conditions: SequenceFragmentCondition[];
  messageIndices: number[];
}

export interface SequenceTestPath {
  pathType: string;
  steps: SequenceMessage[];
  preconditions: string[];
  initiatingActor: string;
}

export interface UseCaseActor {
  name: string;
  alias: string | null;
  actorType: string;
  stereotype: string | null;
}

export interface UseCaseItem {
  name: string;
  alias: string | null;
  description: string | null;
  xmiId: string | null;
}

export interface UseCaseRelationship {
  source: string;
  target: string;
  relationshipType: string;
  label: string | null;
}

export interface UseCaseSystemBoundary {
  name: string;
  useCaseNames: string[];
}

export interface UseCaseScenarioStep {
  sequence: number;
  action: string;
  actor: string;
  target: string | null;
}

export interface UseCaseScenario {
  useCaseName: string;
  primaryActor: string;
  preconditions: string[];
  steps: UseCaseScenarioStep[];
  expectedResult: string;
  scenarioType: string;
}

export type Visibility = "+" | "-" | "#" | "~";

export interface ClassParameter {
  name: string;
  type: string | null;
  defaultValue: string | null;
}

export interface ClassAttribute {
  name: string;
  type: string | null;
  visibility: Visibility;
  isStatic: boolean;
  isReadonly: boolean;
  defaultValue: string | null;
}

export interface ClassMethod {
  name: string;
  parameters: ClassParameter[];
  returnType: string | null;
  visibility: Visibility;
  isAbstract: boolean;
  isStatic: boolean;
}

export interface ClassElement {
  elementKind: "class" | "interface" | "enum";
  name: string;
  isAbstract?: boolean;
  attributes?: ClassAttribute[];
  methods?: ClassMethod[];
  values?: string[];
  package: string | null;
}

export interface ClassMultiplicity {
  sourceEnd: string | null;
  targetEnd: string | null;
  sourceRole: string | null;
  targetRole: string | null;
}

export interface ClassRelationship {
  source: string;
  target: string;
  relationshipType: string;
  label: string | null;
  multiplicity: ClassMultiplicity | null;
}

export interface ClassPackage {
  name: string;
  classNames: string[];
}

export interface ClassMatch {
  diagramClass: string;
  codeClass: string;
  /** `null` = unassessable (OCR/visual diagram extracted no members) — not a vacuous 100 % (Story 3-1b closure). */
  attributeMatchPct: number | null;
  methodMatchPct: number | null;
}

export interface Discrepancy {
  type: string;
  className: string;
  details: string;
  severity: "info" | "warning" | "error";
}

export interface DiagramCodeComparison {
  diagramId: string;
  matchingClasses: ClassMatch[];
  diagramOnlyClasses: string[];
  codeOnlyClasses: string[];
  discrepancies: Discrepancy[];
}

export type ActivityNodeType =
  | "start"
  | "stop"
  | "action"
  | "decision"
  | "merge"
  | "fork"
  | "join";

export interface ActivityNode {
  id: string;
  name: string;
  nodeType: ActivityNodeType;
  swimlane: string | null;
}

export interface ActivityEdge {
  id: string;
  sourceId: string;
  targetId: string;
  guard: string | null;
  label: string | null;
}

export interface ActivitySwimlane {
  name: string;
  nodeIds: string[];
}

export interface ActivityPathStep {
  nodeId: string;
  name: string;
  nodeType: ActivityNodeType;
  swimlane: string | null;
  guard: string | null;
}

export interface ActivityScenario {
  pathId: string;
  scenarioType: string;
  steps: ActivityPathStep[];
  preconditions: string[];
  expectedResult: string;
}

export interface StateNode {
  id: string;
  name: string;
  isInitial: boolean;
  isFinal: boolean;
  entryAction: string | null;
  doAction: string | null;
  exitAction: string | null;
  parentStateId: string | null;
}

export interface StateTransition {
  id: string;
  sourceId: string;
  targetId: string;
  event: string | null;
  guard: string | null;
  action: string | null;
}

export interface CompositeState {
  id: string;
  name: string;
  childIds: string[];
  internalTransitionIds: string[];
}

export interface StateScenario {
  scenarioId: string;
  scenarioType: string;
  title: string;
  steps: string[];
  sourceState: string | null;
  event: string | null;
  guard: string | null;
  action: string | null;
  targetState: string | null;
  expectedResult: string;
  isNegative: boolean;
}

export interface UMLParsedModel {
  diagramId: string;
  diagramType: DiagramType | null;
  participants: SequenceParticipant[] | null;
  elements: unknown[] | null;
  relationships: SequenceMessage[] | null;
  fragments: SequenceFragment[] | null;
  flows: SequenceTestPath[] | null;
  /** How the model was produced — structural parser (Tier 1) vs OCR (Tier 2, Story 3.1b). */
  source: "parser" | "ocr" | null;
  /** OCR detection confidence (0.0–1.0); `null` for structural (Tier 1) models. */
  confidence: number | null;
}

export interface UMLParseTask {
  diagramId: string;
  taskId: string | null;
  status: string;
}

export interface UMLDiagramDetail {
  diagram: UMLDiagram;
  parsedModel: UMLParsedModel | null;
}

export type FlowSourceType = "uml" | "gui" | "uml_and_gui";
export type FlowStatus = "draft" | "validated" | "tests_generated";

export interface UserFlowStep {
  id: string | null;
  sequence: number;
  action: string;
  actor: string | null;
  targetElement: string | null;
  expectedResult: string | null;
  sourceDiagramId: string | null;
  source: string;
}

export interface UserFlow {
  id: string | null;
  name: string;
  sourceType: FlowSourceType;
  sourceIds: string[] | null;
  steps: UserFlowStep[];
  status: FlowStatus;
  warnings: string[] | null;
  createdAt: string | null;
}

export interface UserFlowListResponse {
  flows: UserFlow[];
  total: number;
}

export interface CrossAnalysisTask {
  taskId: string | null;
  status: string;
}

@Injectable({ providedIn: "root" })
export class UmlService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  /** Upload UML diagrams. Returns 202 with accepted/rejected breakdown + task ids. */
  uploadUml(
    projectId: string,
    files: File[],
    onProgress?: (progress: number) => void,
  ): Observable<UMLUploadResponse> {
    const formData = new FormData();
    for (const file of files) {
      formData.append("files", file, file.name);
    }

    return this.http
      .post<UMLUploadResponse>(
        `${this.apiUrl}/projects/${projectId}/uml/upload`,
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
            return event.body as UMLUploadResponse;
          }
          return null as unknown as UMLUploadResponse;
        }),
      ) as Observable<UMLUploadResponse>;
  }

  /** Paginated list of a project's UML diagrams. */
  listDiagrams(
    projectId: string,
    page = 1,
    pageSize = 20,
  ): Observable<{ diagrams: UMLDiagram[]; total: number }> {
    const params = new HttpParams()
      .set("page", String(page))
      .set("page_size", String(pageSize));

    return this.http.get<{ diagrams: UMLDiagram[]; total: number }>(
      `${this.apiUrl}/projects/${projectId}/uml`,
      {
        params,
      },
    );
  }

  /** Diagram details plus parsed structural model (if available). */
  getDiagram(
    projectId: string,
    diagramId: string,
  ): Observable<UMLDiagramDetail> {
    return this.http.get<UMLDiagramDetail>(
      `${this.apiUrl}/projects/${projectId}/uml/${diagramId}`,
    );
  }

  /** Force (re)parsing of a specific diagram. Returns 202 + task id. */
  parseDiagram(projectId: string, diagramId: string): Observable<UMLParseTask> {
    return this.http.post<UMLParseTask>(
      `${this.apiUrl}/projects/${projectId}/uml/parse`,
      { diagram_id: diagramId },
    );
  }

  /** Compare a parsed class diagram with the project's source code (Story 3.4). */
  compareCode(
    projectId: string,
    diagramId: string,
  ): Observable<DiagramCodeComparison> {
    return this.http.post<DiagramCodeComparison>(
      `${this.apiUrl}/projects/${projectId}/uml/${diagramId}/compare-code`,
      {},
    );
  }

  /** Launch asynchronous cross-diagram analysis (Story 3.7). Returns 202 + task id. */
  analyzeFlows(
    projectId: string,
    diagramIds?: string[],
  ): Observable<CrossAnalysisTask> {
    return this.http.post<CrossAnalysisTask>(
      `${this.apiUrl}/projects/${projectId}/uml/analyze`,
      {
        diagram_ids: diagramIds ?? null,
      },
    );
  }

  /** Paginated list of reconstructed user flows for a project (Story 3.7). */
  listFlows(
    projectId: string,
    page = 1,
    pageSize = 20,
  ): Observable<UserFlowListResponse> {
    const params = new HttpParams()
      .set("page", String(page))
      .set("page_size", String(pageSize));

    return this.http.get<UserFlowListResponse>(
      `${this.apiUrl}/projects/${projectId}/uml/flows`,
      { params },
    );
  }

  /** User flow details with ordered steps (Story 3.7). */
  getFlow(projectId: string, flowId: string): Observable<UserFlow> {
    return this.http.get<UserFlow>(
      `${this.apiUrl}/projects/${projectId}/uml/flows/${flowId}`,
    );
  }
}
