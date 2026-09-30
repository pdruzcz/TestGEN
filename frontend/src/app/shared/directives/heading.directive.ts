import { Directive, computed, input } from "@angular/core";

/**
 * Story 6.11, AC2 — semantyczny nagłówek na elemencie niebędącym h1-h6.
 * Nadaje `role="heading"` + `aria-level`, gdy ze względów stylistycznych
 * lub strukturalnych nie można użyć natywnego znacznika (preferowane są
 * natywne h1-h6 — dyrektywa jest rozwiązaniem ostatniej szansy).
 *
 * Użycie: `<div appHeading="2">Sekcja</div>` → screen reader czyta
 * element jak nagłówek poziomu 2.
 */
@Directive({
  selector: "[appHeading]",
  standalone: true,
  host: {
    role: "heading",
    "[attr.aria-level]": "level()",
  },
})
export class HeadingDirective {
  /** Poziom nagłówka 1-6 (string lub number z szablonu). */
  readonly appHeading = input.required<number | string>();

  readonly level = computed(() => {
    const parsed = Number(this.appHeading());
    return Number.isInteger(parsed) && parsed >= 1 && parsed <= 6 ? parsed : 2;
  });
}
