import { provideHttpClient, withInterceptors } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { TestBed } from "@angular/core/testing";

import { snakeCaseInterceptor } from "../../../../core/interceptors/snake-case.interceptor";
import { environment } from "../../../../../environments/environment";
import { HealingService } from "./healing.service";

const apiUrl = `${environment.apiUrl}/projects`;

describe("HealingService", () => {
  let service: HealingService;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        HealingService,
        // Serwis zakłada odpowiedzi w camelCase — dostarcza je globalny
        // interceptor, więc test musi go zarejestrować.
        provideHttpClient(withInterceptors([snakeCaseInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    service = TestBed.inject(HealingService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it("should be created", () => {
    expect(service).toBeTruthy();
  });

  describe("heal()", () => {
    it("should POST /tests/heal with snake_case version body", () => {
      service.heal("p1", "v-a", "v-b").subscribe((res) => {
        expect(res.taskId).toBe("task-1");
        expect(res.reportId).toBe("r-1");
      });

      const req = httpTesting.expectOne(`${apiUrl}/p1/tests/heal`);
      expect(req.request.method).toBe("POST");
      expect(req.request.body).toEqual({ version_a: "v-a", version_b: "v-b" });
      req.flush({ task_id: "task-1", report_id: "r-1", status: "pending" });
    });
  });

  describe("getReport()", () => {
    it("should GET /healing/{reportId}", () => {
      service.getReport("p1", "r-1").subscribe((res) => {
        expect(res.id).toBe("r-1");
        expect(res.status).toBe("healed");
        expect(res.items.length).toBe(0);
      });

      const req = httpTesting.expectOne(`${apiUrl}/p1/healing/r-1`);
      expect(req.request.method).toBe("GET");
      req.flush({
        id: "r-1",
        project_id: "p1",
        version_a: "v-a",
        version_b: "v-b",
        status: "healed",
        stats: { total: 1, healed: 1 },
        created_at: "2026-07-17T10:00:00Z",
        items: [],
      });
    });
  });

  describe("decide()", () => {
    it("should POST decision with action body", () => {
      service.decide("p1", "r-1", "i-1", "accept").subscribe((res) => {
        expect(res.applied).toBe(true);
        expect(res.status).toBe("healed");
      });

      const req = httpTesting.expectOne(
        `${apiUrl}/p1/healing/r-1/items/i-1/decision`,
      );
      expect(req.request.method).toBe("POST");
      expect(req.request.body).toEqual({ action: "accept" });
      req.flush({ item_id: "i-1", status: "healed", applied: true });
    });
  });
});
