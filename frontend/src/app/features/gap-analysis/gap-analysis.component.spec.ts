import { describe, it, expect, vi, beforeEach } from "vitest";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { ActivatedRoute } from "@angular/router";
import { HttpClientTestingModule } from "@angular/common/http/testing";
import { GapAnalysisComponent } from "./gap-analysis.component";

describe("GapAnalysisComponent (Epic 5)", () => {
  let fixture: ComponentFixture<GapAnalysisComponent>;
  let component: GapAnalysisComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GapAnalysisComponent, HttpClientTestingModule],
      providers: [
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: { paramMap: { get: () => "test-project-id" } },
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(GapAnalysisComponent);
    component = fixture.componentInstance;
  });

  it("creates the component", () => {
    expect(component).toBeTruthy();
  });

  it("gets projectId from route", () => {
    expect(component.projectId).toBe("test-project-id");
  });

  it("starts with isLoading true", () => {
    expect(component.isLoading()).toBe(true);
  });

  it("has correct displayed columns", () => {
    expect(component.displayedColumns).toEqual([
      "gapType",
      "requirement",
      "codeEntity",
      "score",
      "method",
      "severity",
      "skeleton",
    ]);
  });

  it("translates gap type labels to Polish", () => {
    expect(component.gapTypeLabel("missing")).toBe("Brakujące");
    expect(component.gapTypeLabel("different")).toBe("Różne");
    expect(component.gapTypeLabel("extra")).toBe("Nadmiarowe");
    expect(component.gapTypeLabel("inconsistent")).toBe("Niespójne");
  });

  it("translates severity labels to Polish", () => {
    expect(component.severityLabel("critical")).toBe("Krytyczny");
    expect(component.severityLabel("warning")).toBe("Ostrzeżenie");
    expect(component.severityLabel("info")).toBe("Info");
  });

  it("updates filter signals on change", () => {
    component.onFilterChange("gapType", "missing");
    expect(component.filterGapType()).toBe("missing");

    component.onFilterChange("severity", "critical");
    expect(component.filterSeverity()).toBe("critical");
  });
});
