import { ComponentFixture, TestBed } from "@angular/core/testing";

import { UsageHistoryPoint } from "../../billing.service";
import { UsageChartComponent } from "./usage-chart.component";

const points: UsageHistoryPoint[] = [
  { date: "2026-09-08", value: 3 },
  { date: "2026-09-09", value: 5 },
  { date: "2026-09-10", value: 6 },
];

describe("UsageChartComponent (Story 7.9, AC3/AC6)", () => {
  let fixture: ComponentFixture<UsageChartComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [UsageChartComponent],
    }).compileComponents();
    fixture = TestBed.createComponent(UsageChartComponent);
  });

  it("rysuje linię zużycia gdy ≥2 punkty", () => {
    fixture.componentRef.setInput("points", points);
    fixture.componentRef.setInput("limit", 10);
    fixture.detectChanges();

    const path = fixture.nativeElement.querySelector("path.usage-line");
    expect(path).toBeTruthy();
    expect(path.getAttribute("d")).toContain("L ");
  });

  it("rysuje przerywaną czerwoną linię limitu (AC3)", () => {
    fixture.componentRef.setInput("points", points);
    fixture.componentRef.setInput("limit", 10);
    fixture.detectChanges();

    const limitLine = fixture.nativeElement.querySelector(".limit-line");
    expect(limitLine).toBeTruthy();
    expect(limitLine.getAttribute("class")).toContain("limit-line");
  });

  it("bez limitu nie rysuje linii limitu", () => {
    fixture.componentRef.setInput("points", points);
    fixture.componentRef.setInput("limit", null);
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector(".limit-line")).toBeNull();
  });

  it("komunikat gdy za mało danych (<2 punkty)", () => {
    fixture.componentRef.setInput("points", [{ date: "2026-09-10", value: 1 }]);
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector("path.usage-line")).toBeNull();
    expect(
      fixture.nativeElement.querySelector(".no-data").textContent,
    ).toContain("Brak wystarczających danych");
  });

  it("alternatywa tekstowa — tabela z danymi (AC6)", () => {
    fixture.componentRef.setInput("points", points);
    fixture.detectChanges();

    const rows = fixture.nativeElement.querySelectorAll(".chart-data tbody tr");
    expect(rows.length).toBe(3);
    expect(rows[0].textContent).toContain("2026-09-08");
    expect(rows[0].textContent).toContain("3");
  });

  it("jednostka MB w tabeli dla storage", () => {
    fixture.componentRef.setInput("points", points);
    fixture.componentRef.setInput("valueUnit", " MB");
    fixture.detectChanges();

    const firstRow = fixture.nativeElement.querySelector(
      ".chart-data tbody tr",
    );
    expect(firstRow.textContent).toContain("3 MB");
  });

  it("svg ma role=img i aria-label (AC6)", () => {
    fixture.componentRef.setInput("points", points);
    fixture.componentRef.setInput("limit", 10);
    fixture.detectChanges();

    const svg = fixture.nativeElement.querySelector("svg");
    expect(svg.getAttribute("role")).toBe("img");
    expect(svg.getAttribute("aria-label")).toContain("Wykres liniowy");
    expect(svg.getAttribute("aria-label")).toContain("limit 10");
  });
});
