import { provideNoopAnimations } from "@angular/platform-browser/animations";
import { provideRouter } from "@angular/router";
import { Router } from "@angular/router";
import { TestBed } from "@angular/core/testing";
import { describe, expect, it, vi } from "vitest";

import { LockedFeatureTabComponent } from "./locked-feature-tab.component";

/** Story 7.13 — wzorzec widoczne-zablokowane + WCAG 2.1 AA (NFR25-29). */
describe("LockedFeatureTabComponent (Story 7.13)", () => {
  async function setup(
    inputs?: Partial<{ locked: boolean; requiredPlan: string | null }>,
  ) {
    const navigate = vi.fn();
    await TestBed.configureTestingModule({
      imports: [LockedFeatureTabComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        { provide: Router, useValue: { navigate } },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(LockedFeatureTabComponent);
    if (inputs?.locked !== undefined) {
      fixture.componentRef.setInput("locked", inputs.locked);
    }
    if (inputs?.requiredPlan !== undefined) {
      fixture.componentRef.setInput("requiredPlan", inputs.requiredPlan);
    }
    fixture.detectChanges();
    return { fixture, el: fixture.nativeElement as HTMLElement, navigate };
  }

  it("renderuje kłódkę gdy moduł zablokowany", async () => {
    const { el } = await setup({ locked: true, requiredPlan: "premium" });
    expect(
      el.querySelector('[data-testid="locked-feature-lock"]'),
    ).not.toBeNull();
  });

  it("bez kłódki i atrybutów blokady gdy moduł dostępny", async () => {
    const { el } = await setup({ locked: false, requiredPlan: null });
    expect(el.querySelector('[data-testid="locked-feature-lock"]')).toBeNull();
    expect(
      el.querySelector(".locked-feature-tab")?.getAttribute("aria-disabled"),
    ).toBeNull();
    expect(
      el.querySelector(".locked-feature-tab")?.getAttribute("tabindex"),
    ).toBeNull();
  });

  it("aria-disabled=true i tabindex=0 na zablokowanej kontrolce (focusable, nieaktywna)", async () => {
    const { el } = await setup({ locked: true, requiredPlan: "basic" });
    const tab = el.querySelector(".locked-feature-tab") as HTMLElement;
    expect(tab.getAttribute("aria-disabled")).toBe("true");
    expect(tab.getAttribute("tabindex")).toBe("0");
  });

  it("komunikat PL z nazwą wymaganego planu w aria-label (nie tylko hover)", async () => {
    const { el } = await setup({ locked: true, requiredPlan: "premium" });
    const tab = el.querySelector(".locked-feature-tab") as HTMLElement;
    expect(tab.getAttribute("aria-label")).toContain(
      "Funkcja dostępna w planie Premium",
    );
  });

  it("klik na zablokowanym module = CTA do /billing/plans", async () => {
    const { el, navigate } = await setup({
      locked: true,
      requiredPlan: "basic",
    });
    (el.querySelector(".locked-feature-tab") as HTMLElement).click();
    expect(navigate).toHaveBeenCalledWith(["/billing/plans"]);
  });

  it("klik na dostępnym module nie nawiguje", async () => {
    const { el, navigate } = await setup({ locked: false, requiredPlan: null });
    (el.querySelector(".locked-feature-tab") as HTMLElement).click();
    expect(navigate).not.toHaveBeenCalled();
  });
});
