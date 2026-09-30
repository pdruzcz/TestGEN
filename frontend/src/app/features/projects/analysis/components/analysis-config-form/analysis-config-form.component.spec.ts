import { ComponentFixture, TestBed } from "@angular/core/testing";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { vi } from "vitest";

import { AnalysisConfigFormComponent } from "./analysis-config-form.component";
import {
  AnalysisConfig,
  DEFAULT_ANALYSIS_CONFIG,
} from "../../../services/analysis.service";

describe("AnalysisConfigFormComponent", () => {
  let fixture: ComponentFixture<AnalysisConfigFormComponent>;
  let component: AnalysisConfigFormComponent;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      imports: [AnalysisConfigFormComponent, NoopAnimationsModule],
    });
    fixture = TestBed.createComponent(AnalysisConfigFormComponent);
    fixture.componentRef.setInput("projectId", "proj-1");
    fixture.detectChanges(); // triggers ngOnInit
    component = fixture.componentInstance;
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("mounts with default values", () => {
    expect(component.form).toBeTruthy();
    expect(component.form.controls.modules.value).toEqual(
      DEFAULT_ANALYSIS_CONFIG.modules,
    );
  });

  it("offers Selenium, Playwright and Appium as analysis frameworks (Story 1.56)", () => {
    const values = component.frameworkOptions.map((o) => o.value);
    expect(values).toContain("selenium");
    expect(values).toContain("playwright");
    expect(values).toContain("appium");
  });

  it("offers unittest, TestNG and MSTest as analysis frameworks (Story 1.57)", () => {
    const values = component.frameworkOptions.map((o) => o.value);
    expect(values).toContain("unittest");
    expect(values).toContain("testng");
    expect(values).toContain("mstest");
  });

  it("does NOT render engine mode field — config-only (Story 6.3-zakończenie)", () => {
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).not.toContain("Tryb silnika");
    expect(el.querySelector("mat-radio-group")).toBeNull();
    expect(el.textContent).not.toContain("Opcje zaawansowane LLM");
  });

  it("persists config to localStorage on changes", () => {
    component.form.controls.modules.setValue(["code_analysis", "security"]);

    const raw = localStorage.getItem("testgen:analysis-config:proj-1");
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw!) as AnalysisConfig;
    expect(parsed.modules).toContain("security");
  });

  it("restores config from localStorage on init", () => {
    const persisted: AnalysisConfig = {
      modules: ["security", "documentation"],
      testFramework: "pytest",
    };
    localStorage.setItem(
      "testgen:analysis-config:proj-1",
      JSON.stringify(persisted),
    );

    const newFixture = TestBed.createComponent(AnalysisConfigFormComponent);
    newFixture.componentRef.setInput("projectId", "proj-1");
    newFixture.detectChanges();
    const c = newFixture.componentInstance;

    expect(c.form.controls.modules.value).toEqual(persisted.modules);
    expect(c.form.controls.testFramework.value).toBe("pytest");
  });

  it("ignores stale engineMode/LLM keys persisted before Story 6.3-zakończenie", () => {
    localStorage.setItem(
      "testgen:analysis-config:proj-1",
      JSON.stringify({
        engineMode: "hybrid",
        llmModel: "gpt-4o",
        modules: ["security"],
        testFramework: null,
      }),
    );

    const newFixture = TestBed.createComponent(AnalysisConfigFormComponent);
    newFixture.componentRef.setInput("projectId", "proj-1");
    newFixture.detectChanges();
    const c = newFixture.componentInstance;

    expect(c.form.controls.modules.value).toEqual(["security"]);
    // Po pierwszej zmianie zapis nie zawiera już przestarzałych kluczy
    c.toggleModule("code_analysis", true);
    const raw = localStorage.getItem("testgen:analysis-config:proj-1");
    const parsed = JSON.parse(raw!) as Record<string, unknown>;
    expect(parsed).not.toHaveProperty("engineMode");
    expect(parsed).not.toHaveProperty("llmModel");
  });

  it("emits configChange when form changes", () => {
    const spy = vi.fn();
    component.configChange.subscribe(spy);
    // Clear emissions from ngOnInit
    spy.mockClear();
    component.form.controls.testFramework.setValue("pytest");
    expect(spy).toHaveBeenCalled();
    const last = spy.mock.calls.at(-1)![0] as AnalysisConfig;
    expect(last.testFramework).toBe("pytest");
  });

  it("emits submitConfig with current values when form is submitted", () => {
    const spy = vi.fn();
    component.submitConfig.subscribe(spy);
    component.form.controls.modules.setValue(["code_analysis"]);
    component.onSubmit();
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy.mock.calls[0][0].modules).toEqual(["code_analysis"]);
  });

  it("toggleModule adds and removes from selected modules", () => {
    component.toggleModule("security", true);
    expect(component.form.controls.modules.value).toContain("security");
    component.toggleModule("security", false);
    expect(component.form.controls.modules.value).not.toContain("security");
  });

  it("form is invalid when no modules selected", () => {
    // Remove all modules
    for (const m of DEFAULT_ANALYSIS_CONFIG.modules) {
      component.toggleModule(m, false);
    }
    expect(component.form.controls.modules.valid).toBe(false);
  });
});
