import { HttpClient } from "@angular/common/http";
import { inject, Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { environment } from "../../../../environments/environment";

/** Section classification values emitted by the preprocessing layer. */
export type SectionType =
  | "functional"
  | "non_functional"
  | "instruction"
  | "unclassified";

/**
 * Single section node — a tree entry.
 *
 * Field names are camelCase: the global ``snakeCaseInterceptor`` converts the
 * snake_case API response (``section_id`` → ``sectionId``, …) automatically.
 */
export interface DocSection {
  sectionId: string;
  title: string;
  level: number;
  content: string;
  pageNumber: number | null;
  position: number;
  sectionType: string;
  parentSectionId: string | null;
  children: DocSection[];
}

/** Response of GET /documents/{documentId}/sections (reconstructed tree). */
export interface DocSectionsResponse {
  documentId: string;
  filename: string;
  total: number;
  sections: DocSection[];
}

/** Response of GET /documents/{documentId}/sections/{sectionId}. */
export interface DocSectionDetailResponse {
  documentId: string;
  section: DocSection;
}

/**
 * Service for fetching the document's reconstructed section tree and a single
 * section's detail (Story 2.2 — AC1/AC2).
 */
@Injectable({ providedIn: "root" })
export class DocSectionsService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  getSections(documentId: string): Observable<DocSectionsResponse> {
    return this.http.get<DocSectionsResponse>(
      `${this.apiUrl}/documents/${documentId}/sections`,
    );
  }

  getSectionDetail(
    documentId: string,
    sectionId: string,
  ): Observable<DocSectionDetailResponse> {
    return this.http.get<DocSectionDetailResponse>(
      `${this.apiUrl}/documents/${documentId}/sections/${sectionId}`,
    );
  }
}
