import { Component, inject, signal } from "@angular/core";
import { MatIconModule } from "@angular/material/icon";
import { ThemeService } from "../../services/theme.service";

/**
 * Story 6.10, AC6/AC7 — pasek narzędzi dostępności widoczny na każdej
 * stronie (montowany w app root): przełączniki trybu wysokiego kontrastu
 * i wyłączenia animacji. Preferencje trwałe w localStorage
 * (`testgen:a11y:high-contrast`, `testgen:a11y:reduced-motion`).
 */
@Component({
  selector: "app-accessibility-toolbar",
  standalone: true,
  imports: [MatIconModule],
  templateUrl: "./accessibility-toolbar.component.html",
  styleUrls: ["./accessibility-toolbar.component.scss"],
})
export class AccessibilityToolbarComponent {
  private readonly theme = inject(ThemeService);

  readonly isHighContrast = this.theme.isHighContrastSignal;
  readonly isReducedMotion = this.theme.isReducedMotionSignal;
  readonly expanded = signal(false);

  toggleExpanded(): void {
    this.expanded.update((value) => !value);
  }

  toggleHighContrast(): void {
    this.theme.toggleHighContrast();
  }

  toggleReducedMotion(): void {
    this.theme.toggleReducedMotion();
  }
}
