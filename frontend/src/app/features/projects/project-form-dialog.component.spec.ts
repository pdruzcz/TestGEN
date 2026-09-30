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
import {
  ProjectFormDialogComponent,
  ProjectFormDialogData,
} from "./project-form-dialog.component";

const apiUrl = `${environment.apiUrl}/projects`;

const mockProject: Project = {
  id: "p1",
  tenantId: "t1",
  name: "Istniejący",
  description: "Opis",
  languageHint: "python",
  status: "active",
  createdAt: "2026-04-16T10:00:00Z",
  updatedAt: "2026-04-16T10:00:00Z",
};

function createDialogRefMock() {
  return { close: vi.fn() };
}

async function setup(data: ProjectFormDialogData) {
  const dialogRefMock = createDialogRefMock();

  await TestBed.configureTestingModule({
    imports: [ProjectFormDialogComponent, NoopAnimationsModule],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      { provide: MatDialogRef, useValue: dialogRefMock },
      { provide: MAT_DIALOG_DATA, useValue: data },
    ],
  }).compileComponents();

  const fixture: ComponentFixture<ProjectFormDialogComponent> =
    TestBed.createComponent(ProjectFormDialogComponent);
  fixture.detectChanges();
  const httpTesting = TestBed.inject(HttpTestingController);
  return { fixture, component: fixture.componentInstance, httpTesting, dialogRefMock };
}

describe("ProjectFormDialogComponent", () => {
  afterEach(() => {
    TestBed.inject(HttpTestingController).verify();
  });

  describe("create mode", () => {
    it("should render empty form with create title", async () => {
      const { fixture } = await setup({ mode: "create" });
      const el = fixture.nativeElement as HTMLElement;
      expect(el.querySelector("h2")?.textContent).toContain("Nowy projekt");
    });

    it("should require a name", async () => {
      const { component } = await setup({ mode: "create" });
      expect(component.form.controls.name.hasError("required")).toBe(true);
      expect(component.form.invalid).toBe(true);
    });

    it("should submit POST /projects with payload", async () => {
      const { component, httpTesting, dialogRefMock } = await setup({
        mode: "create",
      });
      component.form.patchValue({
        name: "Nowy projekt",
        description: "Opis testowy",
        languageHint: "python",
      });

      component.onSubmit();

      const req = httpTesting.expectOne(apiUrl);
      expect(req.request.method).toBe("POST");
      expect(req.request.body).toEqual({
        name: "Nowy projekt",
        description: "Opis testowy",
        languageHint: "python",
      });
      req.flush(mockProject);

      expect(dialogRefMock.close).toHaveBeenCalledWith(mockProject);
      expect(component.isSubmitting()).toBe(false);
    });

    it("should convert whitespace-only optional fields to null", async () => {
      const { component, httpTesting } = await setup({ mode: "create" });
      component.form.patchValue({
        name: "Nazwa",
        description: "   ",
        languageHint: "   ",
      });
      component.onSubmit();

      const req = httpTesting.expectOne(apiUrl);
      expect(req.request.body).toEqual({
        name: "Nazwa",
        description: null,
        languageHint: null,
      });
      req.flush(mockProject);
    });

    it("should trim name and reject whitespace-only", async () => {
      const { component, httpTesting } = await setup({ mode: "create" });
      component.form.patchValue({ name: "   " });
      component.onSubmit();
      httpTesting.expectNone(apiUrl);
      expect(component.form.controls.name.hasError("required")).toBe(true);
    });

    it("should show 409 conflict message", async () => {
      const { component, httpTesting } = await setup({ mode: "create" });
      component.form.patchValue({ name: "Zajęta" });
      component.onSubmit();

      const req = httpTesting.expectOne(apiUrl);
      req.flush(
        { detail: "duplicate" },
        { status: 409, statusText: "Conflict" },
      );

      expect(component.errorMessage()).toContain("już istnieje");
      expect(component.isSubmitting()).toBe(false);
    });

    it("should show 429 quota message in Polish", async () => {
      const { component, httpTesting } = await setup({ mode: "create" });
      component.form.patchValue({ name: "Extra" });
      component.onSubmit();

      const req = httpTesting.expectOne(apiUrl);
      req.flush(
        { detail: "Project limit (10) reached for Basic plan" },
        { status: 429, statusText: "Too Many Requests" },
      );

      expect(component.errorMessage()).toContain("Przekroczono limit projektów");
    });

    it("should show 403 forbidden message", async () => {
      const { component, httpTesting } = await setup({ mode: "create" });
      component.form.patchValue({ name: "X" });
      component.onSubmit();
      const req = httpTesting.expectOne(apiUrl);
      req.flush(null, { status: 403, statusText: "Forbidden" });
      expect(component.errorMessage()).toContain("Brak uprawnień");
    });

    it("should show generic error for 500", async () => {
      const { component, httpTesting } = await setup({ mode: "create" });
      component.form.patchValue({ name: "X" });
      component.onSubmit();
      const req = httpTesting.expectOne(apiUrl);
      req.flush(null, { status: 500, statusText: "Server Error" });
      expect(component.errorMessage()).toContain("Nie udało się zapisać");
    });

    it("should close with null on cancel", async () => {
      const { component, dialogRefMock } = await setup({ mode: "create" });
      component.onCancel();
      expect(dialogRefMock.close).toHaveBeenCalledWith(null);
    });
  });

  describe("edit mode", () => {
    it("should prefill form from provided project", async () => {
      const { component, fixture } = await setup({
        mode: "edit",
        project: mockProject,
      });
      expect(component.form.controls.name.value).toBe("Istniejący");
      expect(component.form.controls.description.value).toBe("Opis");
      expect(component.form.controls.languageHint.value).toBe("python");

      const el = fixture.nativeElement as HTMLElement;
      expect(el.querySelector("h2")?.textContent).toContain("Edycja projektu");
    });

    it("should submit PUT /projects/{id}", async () => {
      const { component, httpTesting, dialogRefMock } = await setup({
        mode: "edit",
        project: mockProject,
      });
      component.form.patchValue({ name: "Zmieniony" });
      component.onSubmit();

      const req = httpTesting.expectOne(`${apiUrl}/${mockProject.id}`);
      expect(req.request.method).toBe("PUT");
      expect(req.request.body.name).toBe("Zmieniony");
      req.flush({ ...mockProject, name: "Zmieniony" });

      expect(dialogRefMock.close).toHaveBeenCalledWith({
        ...mockProject,
        name: "Zmieniony",
      });
    });
  });
});
