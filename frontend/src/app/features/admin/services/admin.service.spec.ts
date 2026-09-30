import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { TestBed } from "@angular/core/testing";

import { environment } from "../../../../environments/environment";
import { AdminService } from "./admin.service";

const API = environment.apiUrl;

const USER = {
  id: "u1",
  tenantId: "t1",
  email: "jan@example.com",
  name: "Jan Kowalski",
  role: "user",
  isActive: true,
  isBlocked: false,
  deletedAt: null,
  createdAt: "2026-01-10T08:00:00Z",
  lastLoginAt: "2026-07-20T09:30:00Z",
};

const CONFIG = {
  limits: {
    maxFileSizeMb: 100,
    maxProjectsPerTenant: 50,
    maxUsersPerTenant: 25,
    llmCostLimitUsd: 100,
  },
  llm: {
    provider: "anthropic",
    model: "claude-sonnet-4-20250514",
    temperature: 0.2,
    maxTokens: 4096,
    timeoutSeconds: 60,
  },
  maintenance: { enabled: false, message: "" },
  featureFlags: { aiAssistant: true },
};

describe("AdminService", () => {
  let service: AdminService;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        AdminService,
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });
    service = TestBed.inject(AdminService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  describe("stan początkowy sygnałów", () => {
    it("zaczyna z pustymi kolekcjami", () => {
      expect(service.usersSignal()).toEqual([]);
      expect(service.tenantsSignal()).toEqual([]);
      expect(service.auditLogSignal()).toEqual([]);
      expect(service.configSignal()).toBeNull();
    });

    it("nie jest w stanie ładowania i bez błędu", () => {
      expect(service.isLoadingSignal()).toBe(false);
      expect(service.errorSignal()).toBeNull();
    });
  });

  describe("getUsers()", () => {
    it("pobiera listę użytkowników i zapisuje ją w sygnale", () => {
      service.getUsers().subscribe();
      const req = httpTesting.expectOne((r) => r.url === `${API}/users`);

      expect(req.request.method).toBe("GET");
      expect(req.request.params.get("page")).toBe("1");
      req.flush({ users: [USER], total: 1 });

      expect(service.usersSignal().length).toBe(1);
      expect(service.usersSignal()[0].email).toBe("jan@example.com");
      expect(service.usersTotalSignal()).toBe(1);
    });

    it("przekazuje filtr tenanta i paginację", () => {
      service.getUsers({ page: 2, pageSize: 50, tenantId: "t9" }).subscribe();
      const req = httpTesting.expectOne((r) => r.url === `${API}/users`);

      expect(req.request.params.get("page")).toBe("2");
      expect(req.request.params.get("page_size")).toBe("50");
      expect(req.request.params.get("tenant_id")).toBe("t9");
      req.flush({ users: [], total: 0 });
    });

    it("ustawia komunikat błędu i kończy ładowanie", () => {
      service.getUsers().subscribe({ error: () => undefined });
      httpTesting
        .expectOne((r) => r.url === `${API}/users`)
        .flush(null, { status: 500, statusText: "Server Error" });

      expect(service.isLoadingSignal()).toBe(false);
      expect(service.errorSignal()).toContain("użytkowników");
    });
  });

  describe("operacje na użytkowniku", () => {
    it("createUser() wysyła zaproszenie", () => {
      service
        .createUser({ email: "nowy@example.com", role: "user" })
        .subscribe();
      const req = httpTesting.expectOne(`${API}/users/invite`);

      expect(req.request.method).toBe("POST");
      expect(req.request.body).toEqual({
        email: "nowy@example.com",
        role: "user",
      });
      req.flush({ message: "ok", userId: "u2" });
    });

    it("updateUserRole() zmienia rolę i odświeża sygnał", () => {
      service.usersSignal.set([{ ...USER }]);
      service.updateUserRole("u1", "owner").subscribe();
      const req = httpTesting.expectOne(`${API}/users/u1/role`);

      expect(req.request.method).toBe("PUT");
      expect(req.request.body).toEqual({ role: "owner" });
      req.flush({ ...USER, role: "owner" });

      expect(service.usersSignal()[0].role).toBe("owner");
    });

    it("blockUser() ustawia flagę blokady w sygnale", () => {
      service.usersSignal.set([{ ...USER }]);
      service.blockUser("u1").subscribe();
      const req = httpTesting.expectOne(`${API}/users/u1/block`);

      expect(req.request.method).toBe("POST");
      req.flush({ ...USER, isBlocked: true });

      expect(service.usersSignal()[0].isBlocked).toBe(true);
    });

    it("unblockUser() zdejmuje flagę blokady", () => {
      service.usersSignal.set([{ ...USER, isBlocked: true }]);
      service.unblockUser("u1").subscribe();
      const req = httpTesting.expectOne(`${API}/users/u1/unblock`);

      expect(req.request.method).toBe("POST");
      req.flush({ ...USER, isBlocked: false });

      expect(service.usersSignal()[0].isBlocked).toBe(false);
    });

    it("deleteUser() usuwa wpis z sygnału", () => {
      service.usersSignal.set([{ ...USER }]);
      service.deleteUser("u1").subscribe();
      const req = httpTesting.expectOne(`${API}/users/u1`);

      expect(req.request.method).toBe("DELETE");
      req.flush(null, { status: 204, statusText: "No Content" });

      expect(service.usersSignal()).toEqual([]);
    });
  });

  describe("getTenants()", () => {
    it("pobiera tenantów z metrykami", () => {
      service.getTenants().subscribe();
      const req = httpTesting.expectOne(
        (r) => r.url === `${API}/admin/tenants`,
      );

      expect(req.request.method).toBe("GET");
      req.flush({
        tenants: [
          {
            id: "t1",
            name: "Acme",
            slug: "acme",
            plan: "premium",
            isActive: true,
            createdAt: "2026-01-01T00:00:00Z",
            userCount: 5,
            storageBytes: 2048,
            projectCount: 2,
          },
        ],
        total: 1,
      });

      expect(service.tenantsSignal()[0].userCount).toBe(5);
      expect(service.tenantsTotalSignal()).toBe(1);
    });

    it("przekazuje frazę wyszukiwania", () => {
      service.getTenants({ search: "acme" }).subscribe();
      const req = httpTesting.expectOne(
        (r) => r.url === `${API}/admin/tenants`,
      );

      expect(req.request.params.get("search")).toBe("acme");
      req.flush({ tenants: [], total: 0 });
    });

    it("getTenantDetails() pobiera pojedynczego tenanta", () => {
      service.getTenantDetails("t1").subscribe();
      const req = httpTesting.expectOne(`${API}/admin/tenants/t1`);

      expect(req.request.method).toBe("GET");
      req.flush({
        id: "t1",
        name: "Acme",
        slug: "acme",
        plan: "basic",
        isActive: true,
        createdAt: "2026-01-01T00:00:00Z",
        userCount: 1,
        storageBytes: 0,
        projectCount: 0,
      });

      expect(service.selectedTenantSignal()?.name).toBe("Acme");
    });

    it("getTenantProjects() pobiera projekty tenanta", () => {
      service.getTenantProjects("t1").subscribe();
      const req = httpTesting.expectOne(
        (r) => r.url === `${API}/admin/tenants/t1/projects`,
      );

      expect(req.request.method).toBe("GET");
      req.flush({
        projects: [
          {
            id: "p1",
            name: "API",
            status: "active",
            createdAt: "2026-01-02T00:00:00Z",
          },
        ],
        total: 1,
      });

      expect(service.tenantProjectsSignal()[0].name).toBe("API");
    });
  });

  describe("getAuditLog()", () => {
    it("pobiera wpisy i zapisuje je w sygnale", () => {
      service.getAuditLog().subscribe();
      const req = httpTesting.expectOne(
        (r) => r.url === `${API}/admin/audit-logs`,
      );

      expect(req.request.method).toBe("GET");
      req.flush({
        logs: [
          {
            id: "a1",
            createdAt: "2026-07-20T10:00:00Z",
            tenantId: "t1",
            userId: "u1",
            action: "user.blocked",
            resourceType: "user",
            resourceId: "u2",
            details: null,
            ipAddress: "10.0.0.1",
          },
        ],
        total: 1,
      });

      expect(service.auditLogSignal()[0].action).toBe("user.blocked");
      expect(service.auditLogTotalSignal()).toBe(1);
    });

    it("przekazuje filtry daty, użytkownika i akcji", () => {
      service
        .getAuditLog({
          dateFrom: "2026-01-01T00:00:00Z",
          dateTo: "2026-02-01T00:00:00Z",
          userId: "u1",
          action: "user.blocked",
        })
        .subscribe();
      const req = httpTesting.expectOne(
        (r) => r.url === `${API}/admin/audit-logs`,
      );

      expect(req.request.params.get("date_from")).toBe("2026-01-01T00:00:00Z");
      expect(req.request.params.get("date_to")).toBe("2026-02-01T00:00:00Z");
      expect(req.request.params.get("user_id")).toBe("u1");
      expect(req.request.params.get("action")).toBe("user.blocked");
      req.flush({ logs: [], total: 0 });
    });

    it("pomija puste filtry", () => {
      service.getAuditLog({ action: "" }).subscribe();
      const req = httpTesting.expectOne(
        (r) => r.url === `${API}/admin/audit-logs`,
      );

      expect(req.request.params.has("action")).toBe(false);
      req.flush({ logs: [], total: 0 });
    });

    it("getAuditActions() pobiera listę typów akcji", () => {
      service.getAuditActions().subscribe();
      const req = httpTesting.expectOne(`${API}/admin/audit-logs/actions`);

      req.flush(["user.blocked", "platform.config_updated"]);

      expect(service.auditActionsSignal().length).toBe(2);
    });
  });

  describe("konfiguracja platformy", () => {
    it("getConfig() zapisuje konfigurację w sygnale", () => {
      service.getConfig().subscribe();
      const req = httpTesting.expectOne(`${API}/admin/config`);

      expect(req.request.method).toBe("GET");
      req.flush(CONFIG);

      expect(service.configSignal()?.maintenance.enabled).toBe(false);
      expect(service.configSignal()?.llm.provider).toBe("anthropic");
    });

    it("updateConfig() wysyła tylko zmienione sekcje", () => {
      service
        .updateConfig({ maintenance: { enabled: true, message: "Przerwa" } })
        .subscribe();
      const req = httpTesting.expectOne(`${API}/admin/config`);

      expect(req.request.method).toBe("PUT");
      expect(req.request.body).toEqual({
        maintenance: { enabled: true, message: "Przerwa" },
      });
      req.flush({
        ...CONFIG,
        maintenance: { enabled: true, message: "Przerwa" },
      });

      expect(service.configSignal()?.maintenance.message).toBe("Przerwa");
    });

    it("ustawia komunikat błędu przy nieudanym zapisie", () => {
      service
        .updateConfig({ maintenance: { enabled: true, message: "" } })
        .subscribe({ error: () => undefined });
      httpTesting
        .expectOne(`${API}/admin/config`)
        .flush(null, { status: 422, statusText: "Unprocessable Entity" });

      expect(service.errorSignal()).toContain("konfiguracji");
      expect(service.isLoadingSignal()).toBe(false);
    });
  });
});
