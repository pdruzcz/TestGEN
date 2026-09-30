/**
 * Project DTOs — 1:1 with backend/app/schemas/project.py.
 *
 * Interceptor `snakeCaseInterceptor` automatically converts
 *   - outgoing request bodies: camelCase → snake_case
 *   - incoming response bodies: snake_case → camelCase
 * so interfaces below use camelCase.
 *
 * Query params are NOT transformed — they must be sent as snake_case
 * (see ProjectService.list()).
 */

export type ProjectStatus =
  | "created"
  | "active"
  | "analyzing"
  | "completed"
  | "archived";

export interface Project {
  id: string;
  tenantId: string;
  name: string;
  description: string | null;
  languageHint: string | null;
  status: ProjectStatus;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface ProjectCreatePayload {
  name: string;
  description?: string | null;
  languageHint?: string | null;
}

export interface ProjectUpdatePayload {
  name?: string | null;
  description?: string | null;
  languageHint?: string | null;
}

export interface ProjectListResponse {
  projects: Project[];
  total: number;
}

export interface ProjectListQuery {
  page?: number;
  pageSize?: number;
  status?: ProjectStatus | null;
  language?: string | null;
  sortBy?: "name" | "created_at" | "updated_at" | "status";
  sortOrder?: "asc" | "desc";
}
