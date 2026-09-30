import {
  Directive,
  ElementRef,
  Renderer2,
  RendererStyleFlags2,
  effect,
  inject,
} from "@angular/core";
import { ThemeService } from "../services/theme.service";

/**
 * Story 6.10, AC4 — programowa kontrola animacji na elemencie:
 * gdy aktywna redukcja animacji (toolbar lub `prefers-reduced-motion`),
 * wyłącza `animation` i `transition` inline na hoście. Uzupełnienie
 * globalnych reguł CSS z `_motion.scss` dla elementów animowanych
 * programowo (style inline nadpisują animacje ustawiane z JS).
 */
@Directive({
  selector: "[appReducedMotion]",
  standalone: true,
})
export class ReducedMotionDirective {
  private readonly el = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly renderer = inject(Renderer2);
  private readonly theme = inject(ThemeService);

  constructor() {
    effect(() => {
      const native = this.el.nativeElement;
      if (this.theme.isReducedMotionSignal()) {
        this.renderer.setStyle(
          native,
          "animation",
          "none",
          RendererStyleFlags2.Important,
        );
        this.renderer.setStyle(
          native,
          "transition",
          "none",
          RendererStyleFlags2.Important,
        );
      } else {
        this.renderer.removeStyle(native, "animation");
        this.renderer.removeStyle(native, "transition");
      }
    });
  }
}
