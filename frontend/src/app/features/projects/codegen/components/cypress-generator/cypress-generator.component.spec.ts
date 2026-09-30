import { ComponentFixture, TestBed } from "@angular/core/testing";
import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideRouter } from "@angular/router";

import { CypressGeneratorComponent } from "./cypress-generator.component";
import { environment } from "../../../../../../environments/environment";

describe("CypressGeneratorComponent", () => {
  let fixture: ComponentFixture<CypressGeneratorComponent>;
  let component: CypressGeneratorComponent;
  let httpTesting: HttpTestingController;
  const apiUrl = environment.apiUrl;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [CypressGeneratorComponent],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });
    fixture = TestBed.createComponent(CypressGeneratorComponent);
    fixture.detectChanges();
    component = fixture.componentInstance;
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it("mounts with cypress as default framework", () => {
    expect(component.framework()).toBe("cypress");
    expect(component.selectedOption().buttonLabel).toBe("Cypress");
  });

  it("offers 8 framework options incl. Selenium, Playwright, Appium, unittest, TestNG and MSTest (Stories 1.56/1.57)", () => {
    const values = component.frameworkOptions.map((o) => o.value);
    expect(values).toEqual([
      "cypress",
      "sikulix",
      "selenium",
      "playwright",
      "appium",
      "unittest",
      "testng",
      "mstest",
    ]);

    const el = fixture.nativeElement as HTMLElement;
    const frameworkSelect = el.querySelector<HTMLSelectElement>(
      "select[aria-label='Framework']",
    );
    const optionTexts = Array.from(frameworkSelect?.options ?? []).map((o) =>
      o.textContent?.trim(),
    );
    expect(optionTexts).toContain("Selenium (.py, E2E web)");
    expect(optionTexts).toContain("Playwright (.spec.ts, E2E web)");
    expect(optionTexts).toContain("Appium (.py, E2E mobilne)");
    expect(optionTexts).toContain("unittest (.py, TestCase)");
    expect(optionTexts).toContain("TestNG (.java, adnotacje)");
    expect(optionTexts).toContain("MSTest (.cs, [TestClass])");
  });

  it("updates the generate button label per framework (Story 1.56)", () => {
    component.framework.set("selenium");
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain("Generuj kod Selenium");

    component.framework.set("appium");
    fixture.detectChanges();
    expect(el.textContent).toContain("Generuj kod Appium");
  });

  it("shows platform select only for Appium (Story 1.56)", () => {
    const el = fixture.nativeElement as HTMLElement;
    expect(
      el.querySelector("select[aria-label='Platforma urządzenia']"),
    ).toBeNull();

    component.framework.set("appium");
    fixture.detectChanges();
    expect(
      el.querySelector("select[aria-label='Platforma urządzenia']"),
    ).not.toBeNull();
  });

  it("dispatches POST /codegen/selenium for selenium framework (Story 1.56)", () => {
    component.selectedIds.set(["tc-1", "tc-2"]);
    component.framework.set("selenium");
    component.generate();

    const req = httpTesting.expectOne(
      (r) => r.method === "POST" && r.url.includes("/codegen/selenium"),
    );
    expect(req.request.body).toEqual({
      test_case_ids: ["tc-1", "tc-2"],
      framework: "selenium",
    });
    req.flush({ taskId: "task-sel", status: "pending" });
  });

  it("dispatches POST /codegen/playwright for playwright framework (Story 1.56)", () => {
    component.selectedIds.set(["tc-1"]);
    component.framework.set("playwright");
    component.generate();

    const req = httpTesting.expectOne(
      (r) => r.method === "POST" && r.url.includes("/codegen/playwright"),
    );
    expect(req.request.body).toEqual({
      test_case_ids: ["tc-1"],
      framework: "playwright",
    });
    req.flush({ taskId: "task-pw", status: "pending" });
  });

  it("dispatches POST /codegen/appium with the selected platform (Story 1.56)", () => {
    component.selectedIds.set(["tc-1"]);
    component.framework.set("appium");
    component.platform.set("ios");
    component.generate();

    const req = httpTesting.expectOne(
      (r) => r.method === "POST" && r.url.includes("/codegen/appium"),
    );
    expect(req.request.body).toEqual({
      test_case_ids: ["tc-1"],
      framework: "appium",
      platform: "ios",
    });
    req.flush({ taskId: "task-ap", status: "pending" });
  });

  it("shows an error when generating without selected test cases", () => {
    component.selectedIds.set([]);
    component.generate();

    expect(component.loadError()).toContain("Wybierz co najmniej jeden");
  });

  it("dispatches POST /codegen/unittest for unittest framework (Story 1.57)", () => {
    component.selectedIds.set(["tc-1"]);
    component.framework.set("unittest");
    component.generate();

    const req = httpTesting.expectOne(
      (r) => r.method === "POST" && r.url.includes("/codegen/unittest"),
    );
    expect(req.request.body).toEqual({
      test_case_ids: ["tc-1"],
      framework: "unittest",
    });
    req.flush({ taskId: "task-ut", status: "pending" });
  });

  it("dispatches POST /codegen/testng for testng framework (Story 1.57)", () => {
    component.selectedIds.set(["tc-1"]);
    component.framework.set("testng");
    component.generate();

    const req = httpTesting.expectOne(
      (r) => r.method === "POST" && r.url.includes("/codegen/testng"),
    );
    expect(req.request.body).toEqual({
      test_case_ids: ["tc-1"],
      framework: "testng",
    });
    req.flush({ taskId: "task-tng", status: "pending" });
  });

  it("dispatches POST /codegen/mstest for mstest framework (Story 1.57)", () => {
    component.selectedIds.set(["tc-1"]);
    component.framework.set("mstest");
    component.generate();

    const req = httpTesting.expectOne(
      (r) => r.method === "POST" && r.url.includes("/codegen/mstest"),
    );
    expect(req.request.body).toEqual({
      test_case_ids: ["tc-1"],
      framework: "mstest",
    });
    req.flush({ taskId: "task-mst", status: "pending" });
  });

  it("derives download file name and extension per framework (Stories 1.56/1.57)", () => {
    expect(component.downloadFileName("playwright", null)).toBe("test.spec.ts");
    expect(component.downloadFileName("selenium", null)).toBe("test.py");
    expect(
      component.downloadFileName("cypress", "cypress/e2e/login.cy.ts"),
    ).toBe("login.cy.ts");
    expect(component.downloadFileName("testng", null)).toBe("test.java");
    expect(component.downloadFileName("mstest", null)).toBe("test.cs");
    expect(component.downloadExtension("playwright")).toBe(".spec.ts");
    expect(component.downloadExtension("appium")).toBe(".py");
    expect(component.downloadExtension("unknown-fw")).toBe(".txt");
  });
});
