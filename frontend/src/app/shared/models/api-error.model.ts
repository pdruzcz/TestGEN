/**
 * Typed interface for RFC 7807 API error responses.
 * Used to parse backend error responses consistently across components.
 */
export interface ApiErrorResponse {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  instance?: string;
  [key: string]: unknown;
}
