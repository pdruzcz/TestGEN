import { HttpErrorResponse, HttpInterceptorFn } from "@angular/common/http";
import { Injectable, inject, signal } from "@angular/core";
import { catchError, throwError } from "rxjs";
import {
  ModuleLocksService,
  PlanName,
} from "../../core/services/module-locks.service";

/** Szczegóły odmowy dostępu z 402 `feature_requires_plan` (Story 7.13). */
export interface FeatureLockAlert {
  feature: string;
  requiredPlan: PlanName;
}

/**
 * Stan ostatniej odmowy — sygnał czytany przez FeatureLockedBannerComponent
 * (inline alert w app-root, wzorzec QuotaAlertService z 7.8).
 */
@Injectable({ providedIn: "root" })
export class FeatureLockAlertService {
  private readonly _alert = signal<FeatureLockAlert | null>(null);
  readonly alert = this._alert.asReadonly();

  show(alert: FeatureLockAlert): void {
    this._alert.set(alert);
  }

  dismiss(): void {
    this._alert.set(null);
  }
}

/**
 * Interceptor HTTP (Story 7.13) — przechwytuje 402 `feature_requires_plan`
 * z FeatureGatingService backendu: publikuje alert z CTA do /billing/plans
 * i odświeża blokady modułów (stan mógł się zdezaktualizować po zmianie planu).
 */
export const featureLockInterceptor: HttpInterceptorFn = (req, next) => {
  const alerts = inject(FeatureLockAlertService);
  const moduleLocks = inject(ModuleLocksService);
  return next(req).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse && error.status === 402) {
        const body = error.error as Record<string, unknown> | null;
        if (body && body["error"] === "feature_requires_plan") {
          alerts.show({
            feature: String(body["feature"] ?? ""),
            requiredPlan: String(body["required_plan"] ?? "basic") as PlanName,
          });
          moduleLocks.refresh();
        }
      }
      return throwError(() => error);
    }),
  );
};
