import { ComponentFixture, TestBed } from "@angular/core/testing";
import { provideNoopAnimations } from "@angular/platform-browser/animations";
import { CdkDragDrop } from "@angular/cdk/drag-drop";
import { FormControl } from "@angular/forms";
import { TestCase, TestCaseUpdatePayload } from "../../models/test-case.model";
import {
  TestCaseEditorComponent,
  stepsToItems,
} from "./test-case-editor.component";

function makeTc(overrides: Partial<TestCase> = {}): TestCase {
  return {
    id: "tc-1",
    tenantId: "t1",
    analysisResultId: "ar1",
    sourceFileId: null,
    title: "Test logowania",
    description: "Opis",
    priority: "HIGH",
    type: "UNIT",
    framework: "PYTEST",
    status: "DRAFT",
    language: "python",
    testCode: null,
    imports: null,
    setupCode: null,
    teardownCode: null,
    preconditions: null,
    steps: { items: ["Otwórz stronę", "Zaloguj się"] },
    expectedResult: "Użytkownik zalogowany",
    testData: null,
    sourceFunction: null,
    sourceClass: null,
    sourceEndpoint: null,
    scenarioDescription: null,
    scenarioRationale: null,
    edgeCaseDescription: null,
    confidenceScore: null,
    tags: null,
    isEdited: false,
    reviewedAt: null,
    reviewedBy: null,
    lastExecutedAt: null,
    lastExecutionResult: null,
    executionCount: 0,
    passCount: 0,
    failCount: 0,
    createdAt: null,
    updatedAt: null,
    ...overrides,
  };
}

describe("stepsToItems", () => {
  it("parses dict format {items: []}", () => {
    expect(stepsToItems({ items: ["a", "b"] })).toEqual(["a", "b"]);
  });

  it("parses legacy string format with numbering", () => {
    expect(stepsToItems("1. Krok pierwszy\n2) Krok drugi\n")).toEqual([
      "Krok pierwszy",
      "Krok drugi",
    ]);
  });

  it("returns empty array for null/empty", () => {
    expect(stepsToItems(null)).toEqual([]);
    expect(stepsToItems({})).toEqual([]);
  });
});

describe("TestCaseEditorComponent", () => {
  let fixture: ComponentFixture<TestCaseEditorComponent>;
  let component: TestCaseEditorComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TestCaseEditorComponent],
      providers: [provideNoopAnimations()],
    }).compileComponents();

    fixture = TestBed.createComponent(TestCaseEditorComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput("testCase", makeTc());
    fixture.detectChanges();
  });

  it("initializes the form from the test case (AC4)", () => {
    expect(component.form.controls.title.value).toBe("Test logowania");
    expect(component.stepsArray.length).toBe(2);
    expect(component.form.controls.status.value).toBe("DRAFT");
  });

  it("adds and removes steps", () => {
    component.addStep();
    expect(component.stepsArray.length).toBe(3);
    component.removeStep(2);
    expect(component.stepsArray.length).toBe(2);
  });

  it("reorders steps via drag-drop with renumbering (AC6)", () => {
    component.onStepDrop({
      previousIndex: 0,
      currentIndex: 1,
    } as CdkDragDrop<FormControl<string>[]>);
    expect(component.stepsArray.at(0).value).toBe("Zaloguj się");
    expect(component.stepsArray.at(1).value).toBe("Otwórz stronę");
  });

  it("emits payload with steps as {items: []} on save", () => {
    let payload: TestCaseUpdatePayload | undefined;
    component.save.subscribe((p: TestCaseUpdatePayload) => (payload = p));

    component.form.controls.title.setValue("Zmieniony tytuł");
    component.submit();

    expect(payload?.title).toBe("Zmieniony tytuł");
    expect(payload?.steps).toEqual({
      items: ["Otwórz stronę", "Zaloguj się"],
    });
    expect(payload?.expectedResult).toBe("Użytkownik zalogowany");
  });

  it("does not emit when title is empty", () => {
    let emitted = false;
    component.save.subscribe(() => (emitted = true));
    component.form.controls.title.setValue("");
    component.submit();
    expect(emitted).toBe(false);
  });

  it("emits cancelEdit on Escape (AC8)", () => {
    let cancelled = false;
    component.cancelEdit.subscribe(() => (cancelled = true));
    component.onEscape(new KeyboardEvent("keydown", { key: "Escape" }));
    expect(cancelled).toBe(true);
  });
});
