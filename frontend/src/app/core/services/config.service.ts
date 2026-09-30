import { HttpClient } from "@angular/common/http";
import { Injectable, inject, signal } from "@angular/core";
import { environment } from "../../../environments/environment";

export interface SystemConfig {
  engineMode: string;
}

/**
 * Serwis konfiguracji systemowej — pobiera publiczne ustawienia backendu.
 * engine_mode to cecha konfiguracji systemu, nie wybór użytkownika.
 */
@Injectable({ providedIn: "root" })
export class ConfigService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  /** Konfiguracja systemu. Domyślnie LLM (aktualna konfiguracja produkcyjna). */
  readonly configSignal = signal<SystemConfig>({ engineMode: "llm" });

  private loaded = false;

  loadConfig(): void {
    if (this.loaded) return;
    this.loaded = true;
    this.http.get<SystemConfig>(`${this.apiUrl}/config`).subscribe({
      next: (config) => this.configSignal.set(config),
      error: () => {
        // Fallback — przy błędzie użyj trybu natywnego
        this.configSignal.set({ engineMode: "native" });
      },
    });
  }
}

/** Map a configured engine_mode value to a Polish display label. */
export function engineModeLabel(mode: string): string {
  switch (mode) {
    case "native":
      return "Natywna";
    case "llm":
      return "LLM";
    case "hybrid":
      return "Hybrydowa";
    default:
      return mode;
  }
}
