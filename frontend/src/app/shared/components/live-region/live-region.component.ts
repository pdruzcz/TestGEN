import { Component, input } from "@angular/core";

/**
 * Story 6.11, AC3 — reużywalny live region: ogłasza screen readerowi
 * zmiany przekazanego komunikatu. `aria-atomic="true"` — komunikat
 * czytany w całości przy każdej zmianie.
 *
 * Użycie deklaratywne (w szablonie, dla statusów widocznych lub nie):
 * `<app-live-region [message]="statusText()" priority="polite" />`
 * Dla ogłoszeń imperatywnych z kodu — `LiveAnnouncerService`.
 */
@Component({
  selector: "app-live-region",
  standalone: true,
  template: `
    <div
      class="visually-hidden"
      [attr.aria-live]="priority()"
      aria-atomic="true"
      [attr.role]="priority() === 'assertive' ? 'alert' : 'status'"
    >
      {{ message() }}
    </div>
  `,
})
export class LiveRegionComponent {
  /** Komunikat do ogłoszenia — każda zmiana wartości jest odczytywana. */
  readonly message = input<string>("");

  /** polite — statusy/postęp; assertive — błędy. */
  readonly priority = input<"polite" | "assertive">("polite");
}
