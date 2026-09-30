import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { TestBed } from "@angular/core/testing";
import { ActivatedRoute } from "@angular/router";

import { environment } from "../../../../environments/environment";
import { HealingComponent } from "./healing.component";

const apiUrl = `${environment.apiUrl}/projects`;

describe("HealingComponent", () => {
  let comp: HealingComponent;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: { get: () => "p1" } } },
        },
      ],
    });
    comp = TestBed.runInInjectionContext(() => new HealingComponent());
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpTesting.verify());

  describe("confidenceClass()", () => {
    it("maps thresholds to high/mid/low", () => {
      expect(comp.confidenceClass(0.92)).toBe("conf-high");
      expect(comp.confidenceClass(0.8)).toBe("conf-high");
      expect(comp.confidenceClass(0.64)).toBe("conf-mid");
      expect(comp.confidenceClass(0.4)).toBe("conf-mid");
      expect(comp.confidenceClass(0.1)).toBe("conf-low");
    });
  });

  describe("strategyLabel()", () => {
    it("translates known strategies and null", () => {
      expect(comp.strategyLabel("role+name")).toBe("rola + nazwa");
      expect(comp.strategyLabel("css")).toBe("CSS");
      expect(comp.strategyLabel(null)).toBe("—");
    });
  });

  describe("statusLabel()", () => {
    it("translates statuses to Polish", () => {
      expect(comp.statusLabel("needs_review")).toBe("Do przeglądu");
      expect(comp.statusLabel("healed")).toBe("Naprawiony");
    });
  });

  describe("canLaunch()", () => {
    it("is false when empty", () => {
      expect(comp.canLaunch()).toBe(false);
    });

    it("is false when versions are equal", () => {
      comp.versionA.set("v1");
      comp.versionB.set("v1");
      expect(comp.canLaunch()).toBe(false);
    });

    it("is true when versions differ", () => {
      comp.versionA.set("v1");
      comp.versionB.set("v2");
      expect(comp.canLaunch()).toBe(true);
    });
  });

  describe("launch()", () => {
    it("posts heal then loads the report", () => {
      comp.projectId.set("p1");
      comp.versionA.set("v1");
      comp.versionB.set("v2");
      comp.launch();

      const healReq = httpTesting.expectOne(`${apiUrl}/p1/tests/heal`);
      expect(healReq.request.method).toBe("POST");
      healReq.flush({ taskId: "t1", reportId: "r1", status: "pending" });

      expect(comp.isLaunching()).toBe(false);

      const getReq = httpTesting.expectOne(`${apiUrl}/p1/healing/r1`);
      expect(getReq.request.method).toBe("GET");
      getReq.flush({
        id: "r1",
        projectId: "p1",
        versionA: "v1",
        versionB: "v2",
        status: "healed",
        stats: { total: 1, healed: 1, healthy: 0, avg_confidence: 0.9 },
        createdAt: "2026-07-21T10:00:00Z",
        items: [],
      });

      expect(comp.report()?.status).toBe("healed");
    });
  });

  describe("ngOnInit()", () => {
    it("loads GUI analyses for the version selectors", () => {
      comp.ngOnInit();
      const req = httpTesting.expectOne(`${apiUrl}/p1/gui/analyses`);
      expect(req.request.method).toBe("GET");
      req.flush({
        analyses: [
          {
            id: "a1",
            sourceType: "dom",
            createdAt: "2026-07-29T10:00:00Z",
            versionLabel: "po",
            sourceLabel: "logowanie.html",
            screenSequence: null,
            componentCount: 8,
          },
        ],
        total: 1,
        page: 1,
        pageSize: 20,
      });
      expect(comp.analyses().length).toBe(1);
      expect(comp.analyses()[0].id).toBe("a1");
    });
  });

  describe("analysisLabel()", () => {
    it("formats a DOM analysis with source, label and version", () => {
      const label = comp.analysisLabel({
        id: "a1",
        sourceType: "dom",
        createdAt: "2026-07-29T10:00:00Z",
        versionLabel: "po",
        sourceLabel: "logowanie.html",
        screenSequence: null,
        componentCount: 8,
      });
      expect(label).toContain("DOM");
      expect(label).toContain("logowanie.html");
      expect(label).toContain("po");
    });

    it("labels screenshot analyses as 'zrzut'", () => {
      const label = comp.analysisLabel({
        id: "a2",
        sourceType: "screenshot",
        createdAt: null,
        versionLabel: null,
        sourceLabel: "screen.png",
        screenSequence: 1,
        componentCount: 3,
      });
      expect(label).toContain("zrzut");
    });
  });
});
