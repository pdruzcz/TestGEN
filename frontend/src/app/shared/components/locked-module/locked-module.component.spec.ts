import { provideNoopAnimations } from "@angular/platform-browser/animations";
import { provideRouter } from "@angular/router";
import { TestBed } from "@angular/core/testing";
import { describe, expect, it } from "vitest";

import { LockedModuleComponent } from "./locked-module.component";
import { ModuleLocksService } from "../../../core/services/module-locks.service";

/** Story 7.13 — treść zakładki zablokowanego modułu (banner + panel upsell). */
describe("LockedModuleComponent (Story 7.13)", () => {
  async function setup(moduleKey: string) {
    const fixture = TestBed.createComponent(LockedModuleComponent);
    fixture.componentRef.setInput("moduleKey", moduleKey);
    fixture.componentRef.setInput("title", "Skanowanie bezpieczeństwa");
    fixture.componentRef.setInput(
      "description",
      "Opis modułu dla użytkownika.",
    );
    fixture.detectChanges();
    await fixture.whenStable();
    return { fixture, el: fixture.nativeElement as HTMLElement };
  }

  beforeEach(async () => {
    const locks = {
      isLocked: () => true,
      requiredPlanOf: () => "premium",
      locks: () => ({}),
      currentPlan: () => "freemium",
      ensureLoaded: () => undefined,
      refresh: () => undefined,
    };
    await TestBed.configureTestingModule({
      imports: [LockedModuleComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        { provide: ModuleLocksService, useValue: locks },
      ],
    }).compileComponents();
  });

  it("banner z komunikatem o wymaganym planie (PL)", async () => {
    const { el } = await setup("security");
    const banner = el.querySelector('[data-testid="locked-module-banner"]');
    expect(banner).not.toBeNull();
    expect(banner?.textContent).toContain("Funkcja dostępna w planie Premium");
  });

  it("panel upsell z tytułem modułu i opisem (wniosek FEPW: funkcja opisana)", async () => {
    const { el } = await setup("security");
    const panel = el.querySelector('[data-testid="locked-module-panel"]');
    expect(panel?.textContent).toContain("Skanowanie bezpieczeństwa");
    expect(panel?.textContent).toContain("Opis modułu dla użytkownika.");
  });

  it("CTA prowadzi do /billing/plans", async () => {
    const { el } = await setup("security");
    const cta = el.querySelector<HTMLAnchorElement>(
      '[data-testid="locked-module-cta"]',
    );
    expect(cta?.getAttribute("href")).toBe("/billing/plans");
  });
});
