import { ComponentFixture, TestBed } from "@angular/core/testing";
import { provideNoopAnimations } from "@angular/platform-browser/animations";
import { ResultsFilters } from "../../services/results.service";
import { FilterPanelComponent } from "./filter-panel.component";

describe("FilterPanelComponent", () => {
  let fixture: ComponentFixture<FilterPanelComponent>;
  let component: FilterPanelComponent;

  // Aplikacja jest zoneless (brak zone.js), więc fakeAsync/tick nie działa —
  // debounce RxJS sterujemy fake timerami vitest.
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FilterPanelComponent],
      providers: [provideNoopAnimations()],
    }).compileComponents();

    fixture = TestBed.createComponent(FilterPanelComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it("should create", () => {
    expect(component).toBeTruthy();
  });

  it("emits search query after 300ms debounce (AC4)", () => {
    const emitted: string[] = [];
    component.searchChange.subscribe((v: string) => emitted.push(v));

    component.searchControl.setValue("sql");
    vi.advanceTimersByTime(200);
    expect(emitted).toEqual([]);
    vi.advanceTimersByTime(100);
    expect(emitted).toEqual(["sql"]);
  });

  it("emits filters on severity change (AC2)", () => {
    let last: ResultsFilters | undefined;
    component.filtersChange.subscribe((f: ResultsFilters) => (last = f));

    component.onSeveritiesChange(["critical", "high"]);
    expect(last?.severities).toEqual(["critical", "high"]);
  });

  it("emits filters on type, module and status changes", () => {
    let last: ResultsFilters | undefined;
    component.filtersChange.subscribe((f: ResultsFilters) => (last = f));

    component.onTypeChange("sast");
    expect(last?.type).toBe("sast");
    component.onModuleChange("backend");
    expect(last?.module).toBe("backend");
    component.onStatusChange("accepted");
    expect(last?.status).toBe("accepted");
    // Previous selections are preserved.
    expect(last?.type).toBe("sast");
  });

  it("emits file filter after debounce", () => {
    let last: ResultsFilters | undefined;
    component.filtersChange.subscribe((f: ResultsFilters) => (last = f));

    component.fileControl.setValue("db.py");
    vi.advanceTimersByTime(300);
    expect(last?.file).toBe("db.py");
  });

  it("clearFilters resets everything and emits empty filters", () => {
    let last: ResultsFilters | undefined;
    component.filtersChange.subscribe((f: ResultsFilters) => (last = f));

    component.onSeveritiesChange(["critical"]);
    component.clearFilters();
    vi.advanceTimersByTime(300);
    expect(last?.severities).toEqual([]);
    expect(last?.type).toBeNull();
    expect(component.searchControl.value).toBe("");
  });
});
