import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';

/** Klient generatora konfiguracji CI/CD (Story 8.4). */

export type CicdPlatform = 'jenkins' | 'github_actions' | 'azure_devops' | 'gitlab_ci';
export type SeverityThreshold = 'critical' | 'high' | 'medium';
export type EngineMode = 'native' | 'llm' | 'hybrid';

export interface CicdTemplateInfo {
  platform: CicdPlatform;
  label: string;
  filename: string;
  language: string;
  description: string;
  /** Jak dodać klucz API w danej platformie — treść różni się per CI. */
  secretHint: string;
}

export interface CicdTemplateList {
  platforms: CicdTemplateInfo[];
  availableModules: string[];
  availableEngineModes: EngineMode[];
  availableThresholds: SeverityThreshold[];
  apiKeyVariable: string;
}

export interface CicdGeneratePayload {
  platform: CicdPlatform;
  severityThreshold: SeverityThreshold;
  modules: string[];
  engineMode: EngineMode;
  timeoutMinutes: number;
}

export interface CicdConfig {
  platform: CicdPlatform;
  filename: string;
  language: string;
  content: string;
  secretHint: string;
}

@Injectable({ providedIn: 'root' })
export class CicdService {
  private readonly http = inject(HttpClient);

  readonly templatesSignal = signal<CicdTemplateInfo[]>([]);
  readonly isLoadingSignal = signal(false);

  private baseUrl(projectId: string): string {
    return `${environment.apiUrl}/projects/${projectId}/ci-cd`;
  }

  getTemplates(projectId: string): Observable<CicdTemplateList> {
    this.isLoadingSignal.set(true);
    return this.http.get<CicdTemplateList>(`${this.baseUrl(projectId)}/templates`).pipe(
      tap({
        next: (result) => {
          this.templatesSignal.set(result.platforms ?? []);
          this.isLoadingSignal.set(false);
        },
        error: () => this.isLoadingSignal.set(false),
      }),
    );
  }

  generateConfig(projectId: string, payload: CicdGeneratePayload): Observable<CicdConfig> {
    return this.http.post<CicdConfig>(`${this.baseUrl(projectId)}/generate`, payload);
  }

  /** Kopiuje treść do schowka; `false` gdy przeglądarka odmówi dostępu. */
  async copyToClipboard(text: string): Promise<boolean> {
    try {
      await navigator.clipboard?.writeText(text);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Pobiera wygenerowany plik.
   *
   * Nazwa pliku bywa ścieżką (`.github/workflows/testgen.yml`); przeglądarka
   * i tak zapisuje do katalogu pobierania, więc bierzemy sam ostatni segment.
   */
  downloadFile(filename: string, content: string): void {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename.split('/').pop() ?? filename;
    link.click();
    URL.revokeObjectURL(url);
  }
}
