import { HttpClient } from "@angular/common/http";
import { Injectable, inject, signal } from "@angular/core";
import { environment } from "../../../environments/environment";

/** Model 3-planowy (CR#2 2026-08-28) — wspólny typ dla gatingu modułów. */
export type PlanName = "freemium" | "basic" | "premium";

/** Polskie etykiety planów do komunikatów upsell (nie hardcoded w szablonach). */
export const PLAN_LABELS: Record<PlanName, string> = {
  freemium: "Freemium",
  basic: "Basic",
  premium: "Premium",
};

/** Status pojedynczego modułu z GET /billing/features (Story 7.13, FR71). */
export interface ModuleLock {
  key: string;
  locked: boolean;
  requiredPlan: PlanName | null;
}

interface FeaturesStatusResponse {
  currentPlan: PlanName;
  modules: ModuleLock[];
}

/**
 * Stan blokad modułów gated (Story 7.13) — wzorzec „widoczne-zablokowane".
 *
 * Root-provided, signals — komponenty czytają `isLocked()`/`requiredPlanOf()`
 * i aktualizują się reaktywnie po `refresh()` (reaktywny unlock po upgrade,
 * bez reloadu strony). Jedyne źródło prawdy: backend `GET /billing/features`
 * (próg per moduł z `subscription_plans.features.gated_modules`, seed 7.1).
 */
@Injectable({ providedIn: "root" })
export class ModuleLocksService {
  private readonly http = inject(HttpClient);

  private readonly _locks = signal<Readonly<Record<string, ModuleLock>>>({});
  private readonly _currentPlan = signal<PlanName | null>(null);
  private _loaded = false;

  /** Mapa key → status modułu (readonly signal). */
  readonly locks = this._locks.asReadonly();

  /** Plan tenanta z ostatniego odczytu (null przed pierwszym załadowaniem). */
  readonly currentPlan = this._currentPlan.asReadonly();

  /** Ładuje status modułów raz na sesję widoku (leniwe, idempotentne). */
  ensureLoaded(): void {
    if (!this._loaded) {
      this.refresh();
    }
  }

  /** Odświeża blokady — po upgrade/downgrade planu (webhook → zmiana planu). */
  refresh(): void {
    this._loaded = true;
    this.http
      .get<FeaturesStatusResponse>(`${environment.apiUrl}/billing/features`)
      .subscribe({
        next: (status) => {
          const map: Record<string, ModuleLock> = {};
          for (const module of status.modules) {
            map[module.key] = module;
          }
          this._locks.set(map);
          this._currentPlan.set(status.currentPlan);
        },
        // Fail-open: brak statusu blokad nie może blokować UI — moduły
        // pozostają dostępne, egzekwowanie i tak robi backend (402).
        error: () => this._locks.set({}),
      });
  }

  /** Czy moduł jest zablokowany dla bieżącego planu tenanta. */
  isLocked(key: string): boolean {
    return this._locks()[key]?.locked ?? false;
  }

  /** Wymagany plan modułu (null → moduł niegated/nieznany). */
  requiredPlanOf(key: string): PlanName | null {
    return this._locks()[key]?.requiredPlan ?? null;
  }
}
