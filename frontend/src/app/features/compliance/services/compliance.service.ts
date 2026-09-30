import { Injectable, inject } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { Observable } from "rxjs";
import { environment } from "../../../../environments/environment";

export interface ComplianceScore {
  score: number;
  totalFindings: number;
  breakdown: Record<string, number>;
}

export interface ModuleScore {
  filePath: string;
  score: number;
  totalFindings: number;
  breakdown: Record<string, number>;
}

export interface FunctionScore {
  codeEntityId: string;
  score: number;
  totalFindings: number;
  breakdown: Record<string, number>;
  filePath: string | null;
  entityName: string | null;
}

export interface ComplianceExportResponse {
  csv: string;
  format: string;
}

@Injectable({ providedIn: "root" })
export class ComplianceService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  getProjectScore(projectId: string): Observable<ComplianceScore> {
    return this.http.get<ComplianceScore>(
      `${this.apiUrl}/projects/${projectId}/compliance`,
    );
  }

  getModuleScores(projectId: string): Observable<ModuleScore[]> {
    return this.http.get<ModuleScore[]>(
      `${this.apiUrl}/projects/${projectId}/compliance/modules`,
    );
  }

  getFunctionScores(projectId: string): Observable<FunctionScore[]> {
    return this.http.get<FunctionScore[]>(
      `${this.apiUrl}/projects/${projectId}/compliance/functions`,
    );
  }

  exportReport(projectId: string): Observable<ComplianceExportResponse> {
    return this.http.post<ComplianceExportResponse>(
      `${this.apiUrl}/projects/${projectId}/compliance/export`,
      {},
    );
  }
}
