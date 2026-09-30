import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ActivatedRoute } from "@angular/router";
import { provideRouter } from "@angular/router";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { describe, expect, it } from "vitest";

import { environment } from "../../../environments/environment";
import { CodeErrorsComponent } from "./code-errors.component";
import { CodeError } from "./services/code-errors.service";

/**
 * Story 5.10 — kategoria „Martwy kod" (chip + podsumowanie) i akcja
 * „Odrzuć" (AC3/AC4). Mocki w camelCase — taka postać dociera do
 * komponentu przez snakeCaseInterceptor (fix 2026-09-21).
 */
describe("CodeErrorsComponent (Story 5.10)", () => {
  let fixture: ComponentFixture<CodeErrorsComponent>;
  let component: CodeErrorsComponent;
  let httpMock: HttpTestingController;

  const deadCodeError: CodeError = {
    id: "e1",
    projectId: "p1",
    sourceFileId: null,
    category: "dead_code",
    message: "Funkcja '_x' nie jest wywoływana nigdzie w projekcie (0 wywołań)",
    filePath: "app.py",
    lineStart: 1,
    lineEnd: 2,
    severity: "warning",
    ruleId: "DEAD_CODE",
    suggestion: "Sprawdź i usuń albo oznacz `@internal`",
    context: null,
    status: "open",
    fingerprint: "app.py:_x:abcd1234",
    createdAt: "2026-09-20T10:00:00Z",
  };

  const listResponse = {
    errors: [deadCodeError],
    total: 1,
    page: 1,
    size: 100,
    summary: {
      totalErrors: 1,
      // klucze dynamiczne po interceptorze: dead_code → deadCode
      byCategory: {
        syntax: 0,
        logic: 0,
        semantic: 0,
        conformance: 0,
        deadCode: 1,
      },
      bySeverity: { critical: 0, warning: 1, info: 0 },
    },
  };

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [CodeErrorsComponent],
      providers: [
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: { get: () => "p1" } } },
        },
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });
    fixture = TestBed.createComponent(CodeErrorsComponent);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    const req = httpMock.expectOne(
      `${environment.apiUrl}/projects/p1/code-errors?size=100`,
    );
    req.flush(listResponse);
    fixture.detectChanges();
  });

  afterEach(() => {
    httpMock.verify();
  });

  it("etykieta PL dla dead_code — Martwy kod (AC3)", () => {
    expect(component.categoryLabel("dead_code")).toBe("Martwy kod");
  });

  it("kategoria dead_code w kartach podsumowania (AC3)", () => {
    expect(component.categoryKeys()).toContain("dead_code");
  });

  it("akcja odrzucenia w kolumnach tabeli (AC4)", () => {
    expect(component.displayedColumns).toContain("actions");
  });

  it("render DOM: karty podsumowania z wartościami (camelCase po interceptorze)", () => {
    const cards: Element[] = [
      ...fixture.nativeElement.querySelectorAll(".summary-card"),
    ];
    const values = cards.map((c) =>
      c.querySelector(".summary-value")?.textContent?.trim(),
    );
    expect(values[0]).toBe("1"); // Razem błędów
    expect(values[5]).toBe("1"); // karta Martwy kod (klucz deadCode w runtime)
  });

  it("categoryCount czyta klucz snake i camel (interceptor zamienia klucze)", () => {
    expect(component.categoryCount("dead_code")).toBe(1); // deadCode w byCategory
    expect(component.categoryCount("syntax")).toBe(0);
    expect(component.categoryCount("nieznany")).toBe(0);
  });

  it("render DOM: wiersz tabeli z chipem Martwy kod (AC3)", () => {
    const rows = fixture.nativeElement.querySelectorAll(
      "mat-row, table tbody tr",
    );
    expect(rows.length).toBe(1);
    const chip = fixture.nativeElement.querySelector(
      ".errors-table .cat-chip.cat-dead_code",
    );
    expect(chip?.textContent?.trim()).toBe("Martwy kod");
  });

  it("dismiss — PATCH false_positive i odświeżenie listy (AC4)", () => {
    component.dismiss({
      ...deadCodeError,
    } as never);

    const patch = httpMock.expectOne(
      `${environment.apiUrl}/projects/p1/code-errors/e1/status`,
    );
    expect(patch.request.method).toBe("PATCH");
    expect(patch.request.body).toEqual({ status: "false_positive" });
    patch.flush({});

    const reload = httpMock.expectOne(
      `${environment.apiUrl}/projects/p1/code-errors?size=100`,
    );
    reload.flush(listResponse);
    expect(component.errors().length).toBe(1);
  });
});
