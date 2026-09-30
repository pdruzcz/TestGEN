import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { TestBed } from "@angular/core/testing";
import { describe, expect, it } from "vitest";

import { environment } from "../../../../environments/environment";
import { CodeErrorsService } from "./code-errors.service";

/** Story 5.10 — kategoria dead_code w skanie + triage PATCH (AC3/AC4). */
describe("CodeErrorsService (Story 5.10)", () => {
  let service: CodeErrorsService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(CodeErrorsService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it("domyślny skan obejmuje dead_code (AC3)", () => {
    service.scan("p1").subscribe();
    const req = httpMock.expectOne(
      `${environment.apiUrl}/projects/p1/code-errors/scan`,
    );
    expect(req.request.method).toBe("POST");
    expect(req.request.body.categories).toContain("dead_code");
    req.flush({ task_id: "t1", status: "pending" });
  });

  it("updateStatus — PATCH false_positive (AC4)", () => {
    service.updateStatus("p1", "e1", "false_positive").subscribe();
    const req = httpMock.expectOne(
      `${environment.apiUrl}/projects/p1/code-errors/e1/status`,
    );
    expect(req.request.method).toBe("PATCH");
    expect(req.request.body).toEqual({ status: "false_positive" });
    req.flush({});
  });
});
