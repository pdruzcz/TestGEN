import { ActivatedRoute } from "@angular/router";
import { provideRouter } from "@angular/router";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { describe, expect, it } from "vitest";
import { of } from "rxjs";

import { ProjectDetailComponent } from "./project-detail.component";
import { ProjectService } from "../services/project.service";
import { ModuleLocksService } from "../../../core/services/module-locks.service";

/** Układ strony projektu w 3 pasmach (makieta testgen.pen, 2026-09):
 * Dane → Akcje → Wyniki; same przyciski stroked (kolor = stan, nie grupa);
 * separatory między pasmami; ikony 18×18. */
describe("ProjectDetailComponent — pasma przycisków", () => {
  let fixture: ComponentFixture<ProjectDetailComponent>;
  let el: HTMLElement;

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [ProjectDetailComponent],
      providers: [
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: { get: () => "p1" } } },
        },
        {
          provide: ProjectService,
          useValue: {
            get: () =>
              of({
                id: "p1",
                name: "Sklep",
                description: "",
                status: "active",
              }),
          },
        },
        {
          provide: ModuleLocksService,
          useValue: {
            ensureLoaded: () => {},
            isLocked: () => false,
            requiredPlanOf: () => null,
          },
        },
      ],
    });
    fixture = TestBed.createComponent(ProjectDetailComponent);
    el = fixture.nativeElement;
    fixture.detectChanges();
  });

  function groups(): HTMLElement[] {
    return Array.from(el.querySelectorAll(".bands > .actions"));
  }

  function labels(group: HTMLElement): string[] {
    return Array.from(group.querySelectorAll("a")).map((a) => {
      const clone = a.cloneNode(true) as HTMLElement;
      clone.querySelectorAll("mat-icon").forEach((i) => i.remove());
      return (clone.textContent || "").replace(/\s+/g, " ").trim();
    });
  }

  it("trzy pasma z etykietami aria w kolejności Dane → Akcje → Wyniki", () => {
    const gs = groups();
    expect(gs.length).toBe(3);
    expect(gs[0].getAttribute("aria-label")).toContain("Dane");
    expect(gs[1].getAttribute("aria-label")).toContain("Akcje");
    expect(gs[2].getAttribute("aria-label")).toContain("Wyniki");
  });

  it("składy pasm: 7 / 7 / 11 przycisków", () => {
    const counts = groups().map((g) => g.querySelectorAll("a").length);
    expect(counts).toEqual([7, 7, 11]);
  });

  it("pasmo Dane: Wgraj pliki, Dokumenty, UML, GUI, Integracje, CI/CD, Import z Jiry", () => {
    expect(labels(groups()[0])).toEqual([
      "Wgraj pliki",
      "Dokumenty",
      "Diagramy UML",
      "Zrzuty ekranu GUI",
      "Integracje",
      // Story 8.4 — generator konfiguracji CI/CD
      "Konfiguracja CI/CD",
      // Story 8.12 — import wymagań z Jiry
      "Import z Jiry",
    ]);
  });

  it("pasmo Akcje zawiera Porównanie wersji i Self-healing (decyzja usera)", () => {
    const a = labels(groups()[1]);
    expect(a).toContain("Porównanie wersji");
    expect(a).toContain("Self-healing");
    expect(a).toContain("Preprocessing");
    expect(a[0]).toBe("Preprocessing");
  });

  it("wszystkie przyciski stroked — kolor nie komunikuje pasma (decyzja usera)", () => {
    const raised = el.querySelectorAll(".bands a.mat-mdc-raised-button").length;
    expect(raised).toBe(0);
    const stroked = el.querySelectorAll(
      ".bands a.mat-mdc-outlined-button",
    ).length;
    expect(stroked).toBe(25);
  });

  it("dwa separatory między pasmami", () => {
    expect(el.querySelectorAll(".bands > .band-separator").length).toBe(2);
  });

  it("ikony na przyciskach 18×18 (na serwerze wychodziły 24px)", () => {
    const icons = el.querySelectorAll<HTMLElement>(".bands mat-icon");
    expect(icons.length).toBe(25);
    const sized = Array.from(icons).filter(
      (i) =>
        getComputedStyle(i).width === "18px" &&
        getComputedStyle(i).height === "18px",
    );
    expect(sized.length).toBe(25);
  });
});
