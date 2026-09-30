import { LiveAnnouncer } from "@angular/cdk/a11y";
import { Injectable, inject } from "@angular/core";

export type AnnouncePriority = "polite" | "assertive";

/**
 * Story 6.11, AC3 — ogłaszanie dynamicznych zmian treści dla screen
 * readerów. Cienka fasada nad CDK `LiveAnnouncer` (utrzymuje pojedynczy
 * live region w DOM), z polityką projektu:
 * - `polite` (domyślnie) — komunikaty niekrytyczne (statusy, postęp),
 * - `assertive` — błędy wymagające natychmiastowej uwagi.
 */
@Injectable({ providedIn: "root" })
export class LiveAnnouncerService {
  private readonly cdkAnnouncer = inject(LiveAnnouncer);

  /** Ogłasza komunikat screen readerowi (polski tekst). */
  announce(
    message: string,
    priority: AnnouncePriority = "polite",
  ): Promise<void> {
    return this.cdkAnnouncer.announce(message, priority);
  }

  /** Skrót dla komunikatów o błędach (przerywa bieżące odczytywanie). */
  announceError(message: string): Promise<void> {
    return this.announce(message, "assertive");
  }

  /** Czyści bieżący komunikat (np. przy zmianie widoku). */
  clear(): void {
    this.cdkAnnouncer.clear();
  }
}
