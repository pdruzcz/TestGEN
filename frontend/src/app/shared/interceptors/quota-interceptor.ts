import { HttpErrorResponse, HttpInterceptorFn } from "@angular/common/http";
import { Injectable, inject, signal } from "@angular/core";
import { catchError, throwError } from "rxjs";

/** Szczegóły przekroczonego limitu z odpowiedzi 429 `limit_reached` (Story 7.8, AC6). */
export interface QuotaAlert {
  resource: string;
  limit: number | null;
  current: number | null;
  plan: string;
}

/**
 * Stan ostatniego przekroczenia limitu — sygnał czytany przez
 * QuotaExceededBannerComponent (inline alert w app-root).
 */
@Injectable({ providedIn: "root" })
export class QuotaAlertService {
  private readonly _alert = signal<QuotaAlert | null>(null);
  readonly alert = this._alert.asReadonly();

  show(alert: QuotaAlert): void {
    this._alert.set(alert);
  }

  dismiss(): void {
    this._alert.set(null);
  }
}

/**
 * Interceptor HTTP (Story 7.8, AC6) — przechwytuje 429 `limit_reached`
 * z QuotaService backendu i publikuje alert z CTA "Uaktualnij plan".
 * Rate limiting (429 `rate_limit_exceeded`) celowo pomijany — to stan
 * przejściowy, nie wymaga upgrade'u planu.
 */
export const quotaInterceptor: HttpInterceptorFn = (req, next) => {
  const alerts = inject(QuotaAlertService);
  return next(req).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse && error.status === 429) {
        const body = error.error as Record<string, unknown> | null;
        if (body && body["error"] === "limit_reached") {
          alerts.show({
            resource: String(body["resource"] ?? ""),
            limit: typeof body["limit"] === "number" ? body["limit"] : null,
            current: typeof body["current"] === "number" ? body["current"] : null,
            plan: String(body["plan"] ?? ""),
          });
        }
      }
      return throwError(() => error);
    }),
  );
};
