import {
  Directive,
  ElementRef,
  booleanAttribute,
  inject,
  input,
  output,
} from "@angular/core";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(", ");

/**
 * Story 6.9, AC2 — reużywalna dyrektywa nawigacji klawiaturą:
 * - `trapFocus` — pułapka Tab wewnątrz kontenera (modale) z zawijaniem,
 * - `Escape` — emisja `escapePressed` (zamykanie),
 * - strzałki góra/dół — przenoszenie fokusu po elementach listy
 *   (`[appKeyboardNavItem]` lub role listitem/option/menuitem).
 */
@Directive({
  selector: "[appKeyboardNav]",
  standalone: true,
  host: {
    "(keydown)": "onKeydown($event)",
  },
})
export class KeyboardNavDirective {
  private readonly el = inject<ElementRef<HTMLElement>>(ElementRef);

  /** Włącza pułapkę Tab wewnątrz elementu (dla modali/dialogów). */
  readonly trapFocus = input(false, { transform: booleanAttribute });

  /** Włącza nawigację strzałkami po elementach listy. */
  readonly arrowNavigation = input(false, { transform: booleanAttribute });

  /** Emitowane po naciśnięciu Escape (np. zamknięcie modala). */
  readonly escapePressed = output<void>();

  onKeydown(event: KeyboardEvent): void {
    switch (event.key) {
      case "Escape":
        this.escapePressed.emit();
        break;
      case "Tab":
        if (this.trapFocus()) {
          this.handleTabTrap(event);
        }
        break;
      case "ArrowDown":
      case "ArrowUp":
        if (this.arrowNavigation()) {
          this.handleArrow(event);
        }
        break;
    }
  }

  private focusableElements(): HTMLElement[] {
    return Array.from(
      this.el.nativeElement.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
    ).filter(
      (element) =>
        !element.hasAttribute("hidden") &&
        element.getAttribute("aria-hidden") !== "true" &&
        element.closest("[hidden]") === null,
    );
  }

  /** Pułapka fokusu: Tab z ostatniego elementu wraca do pierwszego i odwrotnie. */
  private handleTabTrap(event: KeyboardEvent): void {
    const focusable = this.focusableElements();
    if (focusable.length === 0) {
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;

    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }

  /** Strzałki: przenoszenie fokusu po elementach listy z zawijaniem. */
  private handleArrow(event: KeyboardEvent): void {
    const items = Array.from(
      this.el.nativeElement.querySelectorAll<HTMLElement>(
        '[appKeyboardNavItem], [role="listitem"], [role="option"], [role="menuitem"]',
      ),
    );
    if (items.length === 0) {
      return;
    }
    event.preventDefault();
    const currentIndex = items.indexOf(document.activeElement as HTMLElement);
    const delta = event.key === "ArrowDown" ? 1 : -1;
    const nextIndex =
      currentIndex === -1
        ? 0
        : (currentIndex + delta + items.length) % items.length;
    items[nextIndex].focus();
  }
}
