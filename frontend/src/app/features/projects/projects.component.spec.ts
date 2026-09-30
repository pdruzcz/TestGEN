import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { signal, WritableSignal } from "@angular/core";
import { MatDialogRef } from "@angular/material/dialog";
import { provideRouter } from "@angular/router";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { of } from "rxjs";
import { environment } from "../../../environments/environment";
import { AuthService, UserProfile } from "../../core/services/auth.service";
import { NotificationService } from "../../shared/services/notification.service";
import { Project } from "./models/project.model";
import { ProjectsComponent } from "./projects.component";

const apiUrl = `${environment.apiUrl}/projects`;

const mockUserOwner: UserProfile = {
  id: "u1",
  tenantId: "t1",
  email: "owner@test.com",
  name: "Owner",
  role: "owner",
  isActive: true,
  emailVerifiedAt: "2026-01-01T00:00:00Z",
  notificationPreferences: {},
  mfaEnabled: false,
};

const mockUserPlain: UserProfile = { ...mockUserOwner, role: "user" };

const mockProject: Project = {
  id: "p1",
  tenantId: "t1",
  name: "Alpha",
  description: "opis",
  languageHint: "python",
  status: "active",
  createdAt: "2026-04-16T10:00:00Z",
  updatedAt: "2026-04-16T10:00:00Z",
};

function createAuthServiceMock(user: UserProfile | null) {
  return {
    currentUserSignal: signal<UserProfile | null>(
      user,
    ) as WritableSignal<UserProfile | null>,
  };
}

interface DialogMock {
  open: ReturnType<typeof vi.fn>;
}

function createDialogMock(afterClosedValue: unknown = null): DialogMock {
  return {
    open: vi.fn().mockReturnValue({
      afterClosed: () => of(afterClosedValue),
    } as Partial<MatDialogRef<unknown>>),
  };
}

interface SetupOptions {
  user?: UserProfile | null;
  dialog?: DialogMock;
}

async function setup(opts: SetupOptions = {}) {
  const authServiceMock = createAuthServiceMock(opts.user ?? mockUserOwner);
  const dialogMock = opts.dialog ?? createDialogMock();

  await TestBed.configureTestingModule({
    imports: [ProjectsComponent, NoopAnimationsModule],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      provideRouter([]),
      { provide: AuthService, useValue: authServiceMock },
      // Dzwonek w navbarze (Story 7.11) — stub, żeby polling unread-count
      // nie wpadał w httpMock.verify() tych testów.
      {
        provide: NotificationService,
        useValue: { getUnreadCount: () => of({ count: 0 }) },
      },
    ],
  }).compileComponents();

  const fixture: ComponentFixture<ProjectsComponent> =
    TestBed.createComponent(ProjectsComponent);
  // MatDialog is pulled in via MatDialogModule's providers on the component's
  // import graph; overriding it via TestBed providers is unreliable. Instead
  // swap the private field directly on the component instance — the field is
  // only TypeScript-readonly, not runtime-frozen.
  (fixture.componentInstance as unknown as { dialog: DialogMock }).dialog =
    dialogMock;
  const httpTesting = TestBed.inject(HttpTestingController);
  return {
    fixture,
    component: fixture.componentInstance,
    httpTesting,
    authServiceMock,
    dialogMock,
  };
}

function flushInitialLoad(
  httpTesting: HttpTestingController,
  projects: Project[] = [],
) {
  const req = httpTesting.expectOne((r) => r.url === apiUrl);
  req.flush(
    { projects, total: projects.length },
    { headers: { "X-Total-Count": String(projects.length) } },
  );
}

describe("ProjectsComponent", () => {
  afterEach(() => {
    TestBed.inject(HttpTestingController).verify();
  });

  it("should create", async () => {
    const { fixture, httpTesting } = await setup();
    fixture.detectChanges();
    flushInitialLoad(httpTesting, [mockProject]);
    expect(fixture.componentInstance).toBeTruthy();
  });

  it("should load projects on init with default filters", async () => {
    const { fixture, component, httpTesting } = await setup();
    fixture.detectChanges();

    const req = httpTesting.expectOne((r) => r.url === apiUrl);
    expect(req.request.params.get("page")).toBe("1");
    expect(req.request.params.get("page_size")).toBe("20");
    expect(req.request.params.get("sort_by")).toBe("created_at");
    expect(req.request.params.get("sort_order")).toBe("desc");
    expect(req.request.params.has("status")).toBe(false);
    expect(req.request.params.has("language")).toBe(false);

    req.flush(
      { projects: [mockProject], total: 1 },
      { headers: { "X-Total-Count": "1" } },
    );

    expect(component.projects()).toEqual([mockProject]);
    expect(component.total()).toBe(1);
  });

  it("should show empty state when no projects", async () => {
    const { fixture, httpTesting } = await setup();
    fixture.detectChanges();
    flushInitialLoad(httpTesting, []);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain("Brak projektów");
  });

  it("should render the project name in table", async () => {
    const { fixture, httpTesting } = await setup();
    fixture.detectChanges();
    flushInitialLoad(httpTesting, [mockProject]);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain("Alpha");
  });

  it("should hide edit/delete buttons for role=user", async () => {
    const { fixture, component, httpTesting } = await setup({
      user: mockUserPlain,
    });
    fixture.detectChanges();
    flushInitialLoad(httpTesting, [mockProject]);
    fixture.detectChanges();

    expect(component.canManage()).toBe(false);
    const el = fixture.nativeElement as HTMLElement;
    expect(
      el.querySelector('button[data-testid="project-edit-button"]'),
    ).toBeNull();
    expect(
      el.querySelector('button[data-testid="project-delete-button"]'),
    ).toBeNull();
  });

  it("should show edit/delete buttons for role=owner", async () => {
    const { fixture, httpTesting } = await setup({ user: mockUserOwner });
    fixture.detectChanges();
    flushInitialLoad(httpTesting, [mockProject]);
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(
      el.querySelector('button[data-testid="project-edit-button"]'),
    ).not.toBeNull();
    expect(
      el.querySelector('button[data-testid="project-delete-button"]'),
    ).not.toBeNull();
  });

  it("should render 'open files' link routing to /projects/:id/files for any role", async () => {
    const { fixture, httpTesting } = await setup({ user: mockUserPlain });
    fixture.detectChanges();
    flushInitialLoad(httpTesting, [mockProject]);
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const link = el.querySelector<HTMLAnchorElement>(
      'a[data-testid="project-open-button"]',
    );
    expect(link).not.toBeNull();
    // routerLink renders as an href with the resolved path
    expect(link?.getAttribute("href")).toBe("/projects/p1/files");
  });

  it("should reload when a filter changes (debounced)", async () => {
    vi.useFakeTimers();
    try {
      const { fixture, component, httpTesting } = await setup();
      fixture.detectChanges();
      flushInitialLoad(httpTesting, []);

      component.filtersForm.patchValue({ status: "active" });
      vi.advanceTimersByTime(300);

      const req = httpTesting.expectOne((r) => r.url === apiUrl);
      expect(req.request.params.get("status")).toBe("active");
      expect(req.request.params.get("page")).toBe("1");
      req.flush({ projects: [], total: 0 });
    } finally {
      vi.useRealTimers();
    }
  });

  it("should reset to page=1 after filter change", async () => {
    vi.useFakeTimers();
    try {
      const { fixture, component, httpTesting } = await setup();
      fixture.detectChanges();
      flushInitialLoad(httpTesting, []);

      component.page.set(3);
      component.filtersForm.patchValue({ language: "java" });
      vi.advanceTimersByTime(300);

      const req = httpTesting.expectOne((r) => r.url === apiUrl);
      expect(req.request.params.get("page")).toBe("1");
      expect(req.request.params.get("language")).toBe("java");
      req.flush({ projects: [], total: 0 });
      expect(component.page()).toBe(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("should load next page on paginator change", async () => {
    const { fixture, component, httpTesting } = await setup();
    fixture.detectChanges();
    flushInitialLoad(httpTesting, []);

    component.onPageChange({
      pageIndex: 2,
      pageSize: 50,
      length: 200,
      previousPageIndex: 0,
    });

    const req = httpTesting.expectOne((r) => r.url === apiUrl);
    expect(req.request.params.get("page")).toBe("3");
    expect(req.request.params.get("page_size")).toBe("50");
    req.flush({ projects: [], total: 200 });
  });

  it("should open create dialog and reload on success", async () => {
    const dialog = createDialogMock(mockProject);
    const { fixture, component, httpTesting } = await setup({ dialog });
    fixture.detectChanges();
    flushInitialLoad(httpTesting, []);

    component.onCreate();

    expect(dialog.open).toHaveBeenCalled();
    const req = httpTesting.expectOne((r) => r.url === apiUrl);
    req.flush({ projects: [mockProject], total: 1 });
  });

  it("should NOT reload when create dialog is cancelled", async () => {
    const dialog = createDialogMock(null);
    const { fixture, component, httpTesting } = await setup({ dialog });
    fixture.detectChanges();
    flushInitialLoad(httpTesting, []);

    component.onCreate();
    httpTesting.expectNone((r) => r.url === apiUrl);
  });

  it("should open edit dialog and reload on success", async () => {
    const dialog = createDialogMock({ ...mockProject, name: "Zmieniony" });
    const { fixture, component, httpTesting } = await setup({ dialog });
    fixture.detectChanges();
    flushInitialLoad(httpTesting, [mockProject]);

    component.onEdit(mockProject);

    expect(dialog.open).toHaveBeenCalled();
    const req = httpTesting.expectOne((r) => r.url === apiUrl);
    req.flush({ projects: [{ ...mockProject, name: "Zmieniony" }], total: 1 });
  });

  it("should open delete dialog, step back on last row, then reload", async () => {
    const dialog = createDialogMock(true);
    const { fixture, component, httpTesting } = await setup({ dialog });
    fixture.detectChanges();
    flushInitialLoad(httpTesting, [mockProject]);

    component.page.set(2);
    component.onDelete(mockProject);

    const req = httpTesting.expectOne((r) => r.url === apiUrl);
    expect(req.request.params.get("page")).toBe("1");
    req.flush({ projects: [], total: 0 });
    expect(component.page()).toBe(1);
  });

  it("should NOT step back when page=1 on delete", async () => {
    const dialog = createDialogMock(true);
    const { fixture, component, httpTesting } = await setup({ dialog });
    fixture.detectChanges();
    flushInitialLoad(httpTesting, [mockProject]);

    component.onDelete(mockProject);
    const req = httpTesting.expectOne((r) => r.url === apiUrl);
    expect(req.request.params.get("page")).toBe("1");
    req.flush({ projects: [], total: 0 });
    expect(component.page()).toBe(1);
  });

  it("should show error banner when list API fails", async () => {
    const { fixture, component, httpTesting } = await setup();
    fixture.detectChanges();
    const req = httpTesting.expectOne((r) => r.url === apiUrl);
    req.flush(null, { status: 500, statusText: "Server Error" });
    fixture.detectChanges();

    expect(component.errorMessage()).toContain("Nie udało się załadować");
  });

  it("should translate status to Polish label", async () => {
    const { component, fixture, httpTesting } = await setup();
    fixture.detectChanges();
    flushInitialLoad(httpTesting, []);

    expect(component.statusLabel("created")).toBe("Utworzony");
    expect(component.statusLabel("active")).toBe("Aktywny");
    expect(component.statusLabel("analyzing")).toBe("W analizie");
    expect(component.statusLabel("completed")).toBe("Zakończony");
    expect(component.statusLabel("archived")).toBe("Zarchiwizowany");
  });
});
