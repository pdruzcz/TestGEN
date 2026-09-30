import { Directive, ElementRef, Renderer2, inject } from "@angular/core";

/**
 * Story 6.9, AC3 — wskaźnik fokusu zgodny z WCAG 2.1 AA:
 * outline 2px solid o kontraście >= 3:1, widoczny wyłącznie przy
 * nawigacji klawiaturą (odpowiednik :focus-visible), nigdy dla myszy.
 *
 * Kolor zsynchronizowany z shared/constants/wcag.constants.ts
 * (WCAG_COLORS.focusOutline) i shared/styles/_focus.scss.
 */
@Directive({
  selector: "[appFocusVisible]",
  standalone: true,
  host: {
    "(focus)": "onFocus()",
    "(blur)": "onBlur()",
    "(document:mousedown)": "onMousedown()",
    "(document:keydown)": "onKeydown()",
  },
})
export class FocusVisibleDirective {
  private readonly el = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly renderer = inject(Renderer2);

  /** Czy ostatnia interakcja pochodziła z klawiatury. */
  private keyboardInteraction = false;

  onKeydown(): void {
    this.keyboardInteraction = true;
  }

  onMousedown(): void {
    this.keyboardInteraction = false;
  }

  onFocus(): void {
    if (this.keyboardInteraction) {
      const native = this.el.nativeElement;
      this.renderer.setStyle(native, "outline", "2px solid #0b57d0");
      this.renderer.setStyle(native, "outline-offset", "2px");
    }
  }

  onBlur(): void {
    const native = this.el.nativeElement;
    this.renderer.removeStyle(native, "outline");
    this.renderer.removeStyle(native, "outline-offset");
  }
}
