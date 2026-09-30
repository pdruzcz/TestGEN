import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { MatDialog } from "@angular/material/dialog";
import { provideNoopAnimations } from "@angular/platform-browser/animations";
import { of } from "rxjs";

import { environment } from "../../../../../environments/environment";
import { AdminUser } from "../../services/admin.service";
import { UserDialogResult } from "../user-dialog/user-dialog.component";
import { UserManagementComponent } from "./user-management.component";

const API = environment.apiUrl;

const USER: AdminUser = {
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

describe("UserManagementComponent", () => {
  let fixture: ComponentFixture<UserManagementComponent>;
  let component: UserManagementComponent;
  let httpTesting: HttpTestingController;
  let dialogResult: UserDialogResult | undefined;

  beforeEach(() => {
    dialogResult = undefined;
    TestBed.configureTestingModule({
      imports: [UserManagementComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideNoopAnimations(),
        {
          provide: MatDialog,
          useValue: { open: () => ({ afterClosed: () => of(dialogResult) }) },
        },
      ],
    });
    fixture = TestBed.createComponent(UserManagementComponent);
    component = fixture.componentInstance;
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  /** Pierwsze ładowanie: lista użytkowników + lista tenantów do filtra. */
  function initialLoad(users: AdminUser[] = [USER]): void {
    fixture.detectChanges();
    httpTesting
      .expectOne((r) => r.url === `${API}/users`)
      .flush({ users, total: users.length });
    httpTesting
      .expectOne((r) => r.url === `${API}/admin/tenants`)
      .flush({ tenants: [], total: 0 });
    fixture.detectChanges();
  }

  it("pobiera użytkowników przy inicjalizacji", () => {
    initialLoad();

    expect(component.users().length).toBe(1);
    expect(component.total()).toBe(1);
  });

  it("wyświetla komplet kolumn wymaganych przez story", () => {
    initialLoad();

    expect(component.displayedColumns).toEqual([
      "email",
      "name",
      "role",
      "tenant",
      "status",
      "createdAt",
      "lastLoginAt",
      "actions",
    ]);
  });

  it("renderuje wiersz użytkownika w tabeli", () => {
    initialLoad();
    const text: string = fixture.nativeElement.textContent;

    expect(text).toContain("jan@example.com");
    expect(text).toContain("Jan Kowalski");
  });

  it("opisuje status jako Aktywny, Zablokowany lub Nieaktywny", () => {
    initialLoad();

    expect(component.statusLabel(USER)).toBe("Aktywny");
    expect(component.statusLabel({ ...USER, isBlocked: true })).toBe("Zablokowany");
    expect(component.statusLabel({ ...USER, isActive: false })).toBe("Nieaktywny");
  });

  it("filtruje listę po emailu bez odpytywania backendu", () => {
    initialLoad([USER, { ...USER, id: "u2", email: "anna@example.com" }]);

    component.searchControl.setValue("anna");
    fixture.detectChanges();

    expect(component.filteredUsers().map((u) => u.email)).toEqual([
      "anna@example.com",
    ]);
  });

  it("filtruje listę po roli", () => {
    initialLoad([USER, { ...USER, id: "u2", role: "admin" }]);

    component.roleControl.setValue("admin");

    expect(component.filteredUsers().map((u) => u.id)).toEqual(["u2"]);
  });

  it("filtruje listę po statusie", () => {
    initialLoad([USER, { ...USER, id: "u2", isBlocked: true }]);

    component.statusControl.setValue("blocked");

    expect(component.filteredUsers().map((u) => u.id)).toEqual(["u2"]);
  });

  it("sortuje po dacie ostatniego logowania", () => {
    initialLoad([
      USER,
      { ...USER, id: "u2", lastLoginAt: "2026-07-25T09:30:00Z" },
    ]);

    component.onSortChange({ active: "lastLoginAt", direction: "desc" });

    expect(component.filteredUsers().map((u) => u.id)).toEqual(["u2", "u1"]);
  });

  it("zmiana strony odpytuje backend z nową paginacją", () => {
    initialLoad();

    component.onPageChange({ pageIndex: 1, pageSize: 25, length: 40 });
    const req = httpTesting.expectOne((r) => r.url === `${API}/users`);

    expect(req.request.params.get("page")).toBe("2");
    expect(req.request.params.get("page_size")).toBe("25");
    req.flush({ users: [], total: 40 });
  });

  it("dodanie użytkownika wysyła zaproszenie i odświeża listę", () => {
    initialLoad();
    dialogResult = { action: "invite", email: "nowy@example.com", role: "user" };

    component.openCreateDialog();

    const invite = httpTesting.expectOne(`${API}/users/invite`);
    expect(invite.request.body).toEqual({
      email: "nowy@example.com",
      role: "user",
    });
    invite.flush({ message: "ok", userId: "u9" });

    httpTesting
      .expectOne((r) => r.url === `${API}/users`)
      .flush({ users: [USER], total: 1 });
  });

  it("zmiana roli wysyła PUT na endpoint roli", () => {
    initialLoad();
    dialogResult = { action: "update-role", userId: "u1", role: "owner" };

    component.openEditDialog(USER);

    const req = httpTesting.expectOne(`${API}/users/u1/role`);
    expect(req.request.method).toBe("PUT");
    req.flush({ ...USER, role: "owner" });
  });

  it("blokada użytkownika wywołuje endpoint block", () => {
    initialLoad();
    dialogResult = { action: "block", userId: "u1" };

    component.openEditDialog(USER);

    const req = httpTesting.expectOne(`${API}/users/u1/block`);
    expect(req.request.method).toBe("POST");
    req.flush({ ...USER, isBlocked: true });
  });

  it("usunięcie użytkownika wywołuje DELETE", () => {
    initialLoad();
    dialogResult = { action: "delete", userId: "u1" };

    component.openEditDialog(USER);

    const req = httpTesting.expectOne(`${API}/users/u1`);
    expect(req.request.method).toBe("DELETE");
    req.flush(null, { status: 204, statusText: "No Content" });
  });

  it("zamknięcie dialogu bez wyniku nie wysyła żądań", () => {
    initialLoad();
    dialogResult = undefined;

    component.openEditDialog(USER);

    httpTesting.verify();
  });

  it("pokazuje komunikat błędu, gdy pobranie listy się nie powiedzie", () => {
    fixture.detectChanges();
    httpTesting
      .expectOne((r) => r.url === `${API}/users`)
      .flush(null, { status: 500, statusText: "Server Error" });
    httpTesting
      .expectOne((r) => r.url === `${API}/admin/tenants`)
      .flush({ tenants: [], total: 0 });
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain("użytkowników");
  });
});
