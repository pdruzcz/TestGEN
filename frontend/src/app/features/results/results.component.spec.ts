import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { provideNoopAnimations } from "@angular/platform-browser/animations";
import { ActivatedRoute, provideRouter } from "@angular/router";
import { environment } from "../../../environments/environment";
import { ResultsComponent } from "./results.component";
import { ResultsService } from "./services/results.service";

const apiUrl = environment.apiUrl;

function routeStub(projectId: string) {
  return {
    snapshot: {
      paramMap: {
        get: (key: string) => (key === "projectId" ? projectId : null),
      },
    },
  };
}

describe("ResultsComponent", () => {
  let fixture: ComponentFixture<ResultsComponent>;
  let component: ResultsComponent;
  let httpTesting: HttpTestingController;
  let service: ResultsService;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ResultsComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideNoopAnimations(),
        provideRouter([]),
        { provide: ActivatedRoute, useValue: routeStub("p1") },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ResultsComponent);
    component = fixture.componentInstance;
    httpTesting = TestBed.inject(HttpTestingController);
    service = TestBed.inject(ResultsService);
    fixture.detectChanges();
  });

  afterEach(() => {
    // Overview + results requests fired in ngOnInit — drain whatever is pending.
    httpTesting
      .match(() => true)
      .forEach((req) => req.flush({}, { status: 404, statusText: "Not Found" }));
  });

  it("should create and resolve projectId from the route", () => {
    expect(component).toBeTruthy();
    expect(component.projectId()).toBe("p1");
  });

  it("loads results and overview on init", () => {
    const resultsReqs = httpTesting.match(
      (req) =>
        req.url === `${apiUrl}/projects/p1/security-findings` ||
        req.url === `${apiUrl}/projects/p1/gap-findings`,
    );
    expect(resultsReqs.length).toBe(2);
    resultsReqs.forEach((req) =>
      req.flush({}, { status: 404, statusText: "Not Found" }),
    );
  });

  it("renders the six tabs (AC1)", () => {
    const labels: string[] = Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll(".mdc-tab"),
    ).map((el) => (el.textContent ?? "").trim());
    expect(labels.length).toBe(6);
    expect(labels[0]).toContain("Przegląd");
    expect(labels[1]).toContain("Przypadki testowe");
    expect(labels[2]).toContain("Bezpieczeństwo");
    expect(labels[3]).toContain("Luki");
    expect(labels[4]).toContain("Pokrycie");
    expect(labels[5]).toContain("Raport");
  });

  it("splits results by source for security and gap tabs", () => {
    service.resultsSignal.set([
      {
        id: "1",
        source: "security",
        title: "A",
        description: "",
        severity: "high",
        type: "sast",
        filePath: null,
        module: null,
        status: "new",
        codeSnippet: null,
        language: null,
        lineStart: null,
        suggestedFix: null,
      },
      {
        id: "2",
        source: "gap",
        title: "B",
        description: "",
        severity: "low",
        type: "missing",
        filePath: null,
        module: null,
        status: "new",
        codeSnippet: null,
        language: null,
        lineStart: null,
        suggestedFix: null,
      },
    ]);
    expect(component.securityResults().length).toBe(1);
    expect(component.gapResults().length).toBe(1);
  });

  it("toggles selection of a result row", () => {
    const item = {
      id: "1",
      source: "security" as const,
      title: "A",
      description: "",
      severity: "high" as const,
      type: "sast",
      filePath: null,
      module: null,
      status: "new" as const,
      codeSnippet: null,
      language: null,
      lineStart: null,
      suggestedFix: null,
    };
    component.selectResult(item);
    expect(component.selectedResult()?.id).toBe("1");
    component.selectResult(item);
    expect(component.selectedResult()).toBeNull();
  });

  it("computes severity counts for the overview tab", () => {
    service.resultsSignal.set([
      {
        id: "1",
        source: "security",
        title: "A",
        description: "",
        severity: "critical",
        type: "sast",
        filePath: null,
        module: null,
        status: "new",
        codeSnippet: null,
        language: null,
        lineStart: null,
        suggestedFix: null,
      },
    ]);
    expect(component.severityCounts().critical).toBe(1);
    expect(component.severityCounts().low).toBe(0);
  });

  it("resets selection when switching tabs (AC8)", () => {
    component.selectedResult.set({
      id: "1",
      source: "security",
      title: "A",
      description: "",
      severity: "high",
      type: "sast",
      filePath: null,
      module: null,
      status: "new",
      codeSnippet: null,
      language: null,
      lineStart: null,
      suggestedFix: null,
    });
    component.onTabChange(2);
    expect(component.selectedResult()).toBeNull();
    expect(service.activeTabSignal()).toBe(2);
  });
});
