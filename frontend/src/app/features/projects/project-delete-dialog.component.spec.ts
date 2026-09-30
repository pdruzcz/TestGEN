import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { MAT_DIALOG_DATA, MatDialogRef } from "@angular/material/dialog";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { environment } from "../../../environments/environment";
import { Project } from "./models/project.model";
import { ProjectDeleteDialogComponent } from "./project-delete-dialog.component";

const apiUrl = `${environment.apiUrl}/projects`;

const mockProject: Project = {
  id: "p1",
  tenantId: "t1",
  name: "Do usunięcia",
  description: null,
  languageHint: null,
  status: "active",
  createdAt: "2026-04-16T10:00:00Z",
  updatedAt: "2026-04-16T10:00:00Z",
};

async function setup() {
  const dialogRefMock = { close: vi.fn() };

  await TestBed.configureTestingModule({
    imports: [ProjectDeleteDialogComponent, NoopAnimationsModule],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      { provide: MatDialogRef, useValue: dialogRefMock },
      { provide: MAT_DIALOG_DATA, useValue: { project: mockProject } },
    ],
  }).compileComponents();

  const fixture: ComponentFixture<ProjectDeleteDialogComponent> =
    TestBed.createComponent(ProjectDeleteDialogComponent);
  fixture.detectChanges();
  const httpTesting = TestBed.inject(HttpTestingController);
  return { fixture, component: fixture.componentInstance, httpTesting, dialogRefMock };
}

describe("ProjectDeleteDialogComponent", () => {
  afterEach(() => {
    TestBed.inject(HttpTestingController).verify();
  });

  it("should render project name in confirmation", async () => {
    const { fixture } = await setup();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain("Do usunięcia");
  });

  it("should close with false on cancel", async () => {
    const { component, dialogRefMock } = await setup();
    component.onCancel();
    expect(dialogRefMock.close).toHaveBeenCalledWith(false);
  });

  it("should DELETE /projects/{id} on confirm and close with true", async () => {
    const { component, httpTesting, dialogRefMock } = await setup();
    component.onConfirm();

    const req = httpTesting.expectOne(`${apiUrl}/${mockProject.id}`);
    expect(req.request.method).toBe("DELETE");
    req.flush(null, { status: 204, statusText: "No Content" });

    expect(dialogRefMock.close).toHaveBeenCalledWith(true);
    expect(component.isDeleting()).toBe(false);
  });

  it("should show 403 message on forbidden", async () => {
    const { component, httpTesting, dialogRefMock } = await setup();
    component.onConfirm();
    const req = httpTesting.expectOne(`${apiUrl}/${mockProject.id}`);
    req.flush(null, { status: 403, statusText: "Forbidden" });

    expect(component.errorMessage()).toContain("Brak uprawnień");
    expect(dialogRefMock.close).not.toHaveBeenCalled();
  });

  it("should show 404 message when project gone", async () => {
    const { component, httpTesting } = await setup();
    component.onConfirm();
    const req = httpTesting.expectOne(`${apiUrl}/${mockProject.id}`);
    req.flush(null, { status: 404, statusText: "Not Found" });
    expect(component.errorMessage()).toContain("nie istnieje");
  });

  it("should show generic error on 500", async () => {
    const { component, httpTesting } = await setup();
    component.onConfirm();
    const req = httpTesting.expectOne(`${apiUrl}/${mockProject.id}`);
    req.flush(null, { status: 500, statusText: "Server Error" });
    expect(component.errorMessage()).toContain("Nie udało się usunąć");
  });

  it("should ignore concurrent confirm clicks while deleting", async () => {
    const { component, httpTesting } = await setup();
    component.onConfirm();
    component.onConfirm(); // second call should be a no-op
    const req = httpTesting.expectOne(`${apiUrl}/${mockProject.id}`);
    req.flush(null, { status: 204, statusText: "No Content" });
  });
});
