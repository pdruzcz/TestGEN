import {
  AfterViewInit,
  Directive,
  ElementRef,
  OnDestroy,
  inject,
} from "@angular/core";

let uniqueId = 0;

/**
 * Story 6.9, AC5 — automatyczne wiązania dostępności formularzy:
 * - label ↔ pole: uzupełnia brakujące `for`/`id` (powiązanie programowe),
 * - błędy walidacji (`mat-error`, `.error-message`, `[role="alert"]`):
 *   nadaje id, ustawia `aria-live="polite"` i dowiązuje do pola
 *   przez `aria-describedby` + `aria-invalid`.
 *
 * Obserwuje DOM (MutationObserver), więc obsługuje błędy pojawiające się
 * dynamicznie podczas walidacji.
 */
@Directive({
  selector: "[appFormAccessibility]",
  standalone: true,
})
export class FormAccessibilityDirective implements AfterViewInit, OnDestroy {
  private readonly el = inject<ElementRef<HTMLElement>>(ElementRef);
  private observer: MutationObserver | null = null;

  ngAfterViewInit(): void {
    this.apply();
    this.observer = new MutationObserver(() => this.apply());
    this.observer.observe(this.el.nativeElement, {
      childList: true,
      subtree: true,
    });
  }

  ngOnDestroy(): void {
    this.observer?.disconnect();
    this.observer = null;
  }

  /** Idempotentne uzupełnienie wiązań label/error w całym kontenerze. */
  private apply(): void {
    const root = this.el.nativeElement;
    this.bindLabels(root);
    this.bindErrors(root);
  }

  private bindLabels(root: HTMLElement): void {
    for (const label of Array.from(root.querySelectorAll("label"))) {
      if (label.htmlFor) {
        continue;
      }
      const control = label.querySelector<HTMLElement>(
        "input, select, textarea",
      );
      if (!control) {
        continue;
      }
      if (!control.id) {
        control.id = `a11y-field-${++uniqueId}`;
      }
      label.htmlFor = control.id;
    }
  }

  private bindErrors(root: HTMLElement): void {
    const fields = Array.from(
      root.querySelectorAll<HTMLElement>(
        ".mat-mdc-form-field, .form-field, [data-a11y-field]",
      ),
    );
    const scopes = fields.length > 0 ? fields : [root];

    for (const scope of scopes) {
      const control = scope.querySelector<HTMLElement>(
        "input, select, textarea",
      );
      const errors = Array.from(
        scope.querySelectorAll<HTMLElement>(
          'mat-error, .mat-mdc-form-field-error, .error-message, [role="alert"]',
        ),
      );

      for (const error of errors) {
        if (!error.id) {
          error.id = `a11y-error-${++uniqueId}`;
        }
        if (!error.getAttribute("aria-live")) {
          error.setAttribute("aria-live", "polite");
        }
      }

      if (!control) {
        continue;
      }

      if (errors.length > 0) {
        const ids = errors.map((error) => error.id).join(" ");
        if (control.getAttribute("aria-describedby") !== ids) {
          control.setAttribute("aria-describedby", ids);
        }
        control.setAttribute("aria-invalid", "true");
      } else if (control.getAttribute("aria-invalid") === "true") {
        control.removeAttribute("aria-invalid");
        control.removeAttribute("aria-describedby");
      }
    }
  }
}
