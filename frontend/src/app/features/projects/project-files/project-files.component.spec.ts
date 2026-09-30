import { TestBed, ComponentFixture } from "@angular/core/testing";
import { signal } from "@angular/core";
import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import {
  ActivatedRoute,
  convertToParamMap,
  provideRouter,
} from "@angular/router";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { MAT_DIALOG_DATA, MatDialogRef } from "@angular/material/dialog";
import { of } from "rxjs";
import { vi, expect } from "vitest";
import { ProjectFilesComponent, formatBytes } from "./project-files.component";
import { SourceFileDeleteDialogComponent } from "./source-file-delete-dialog.component";
import { AuthService, UserProfile } from "../../../core/services/auth.service";
import { environment } from "../../../../environments/environment";

const projectId = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const listUrl = `${environment.apiUrl}/projects/${projectId}/files?page=1&page_size=20`;

function createFile(name: string, content = "content"): File {
  return new File([content], name, { type: "text/plain" });
}

function sourceFileFixture(id = "f1", filename = "service.py") {
  return {
    id,
    projectId,
    filename,
    fileSize: 10,
    mimeType: "text/plain",
    sha256Hash: "a".repeat(64),
    detectedLanguage: null,
    detectedFramework: null,
    isCleanedUp: false,
    createdAt: null,
  };
}

describe("ProjectFilesComponent", () => {
  let component: ProjectFilesComponent;
  let fixture: ComponentFixture<ProjectFilesComponent>;
  let httpTesting: HttpTestingController;
  let roleSignal = signal<UserProfile>({ role: "owner" } as UserProfile);
  // Drives the mocked MatDialog's afterClosed() emission.
  let dialogResult: boolean | undefined;
  const matDialogOpen = vi
    .fn()
    .mockImplementation(() => ({ afterClosed: () => of(dialogResult) }));

  beforeEach(async () => {
    roleSignal = signal<UserProfile>({ role: "owner" } as UserProfile);
    dialogResult = undefined;
    matDialogOpen.mockClear();

    await TestBed.configureTestingModule({
      imports: [ProjectFilesComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: { paramMap: convertToParamMap({ projectId }) },
          },
        },
        { provide: AuthService, useValue: { currentUserSignal: roleSignal } },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ProjectFilesComponent);
    component = fixture.componentInstance;
    // MatDialog is provided via MatDialogModule on the component's import graph;
    // overriding it via TestBed providers is unreliable — swap the field
    // directly on the instance (it is TS-readonly, not runtime-frozen).
    (
      component as unknown as { dialog: { open: typeof matDialogOpen } }
    ).dialog = { open: matDialogOpen };
    httpTesting = TestBed.inject(HttpTestingController);
    fixture.detectChanges();

    // The initial list-load fires in ngOnInit — satisfy it before every test.
    const initial = httpTesting.expectOne(listUrl);
    initial.flush({ files: [], total: 0 });
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it("should create with projectId from route", () => {
    expect(component).toBeTruthy();
    expect(component.projectId()).toBe(projectId);
  });

  it("should expose delete controls when the user is owner/admin", () => {
    expect(component.canDelete()).toBe(true);
    expect(component.displayedColumns()).toContain("actions");
  });

  it("should hide delete controls for a plain user", () => {
    roleSignal.set({ role: "user" } as UserProfile);
    expect(component.canDelete()).toBe(false);
    expect(component.displayedColumns()).not.toContain("actions");
  });

  it("should reject unsupported extensions before any upload", () => {
    const badFile = createFile("bad.exe");

    component["handleFiles"]([badFile]);

    expect(component.rejectedFiles().length).toBe(1);
    expect(component.rejectedFiles()[0].filename).toBe("bad.exe");
    expect(component.uploadError()).toContain("odrzucone");
    httpTesting.expectNone(
      `${environment.apiUrl}/projects/${projectId}/upload`,
    );
  });

  it("should POST accepted files and refresh the list on success", () => {
    const goodFile = createFile("service.py");

    component["handleFiles"]([goodFile]);

    const upload = httpTesting.expectOne(
      `${environment.apiUrl}/projects/${projectId}/upload`,
    );
    expect(upload.request.method).toBe("POST");
    expect(upload.request.body).toBeInstanceOf(FormData);
    upload.flush({
      projectId,
      acceptedFiles: [
        {
          id: "f1",
          filename: "service.py",
          fileSize: 10,
          mimeType: "text/plain",
          sha256Hash: "a".repeat(64),
          status: "accepted",
          rejectionReason: null,
        },
      ],
      rejectedFiles: [],
      totalAccepted: 1,
      totalRejected: 0,
    });

    const refresh = httpTesting.expectOne(listUrl);
    refresh.flush({ files: [sourceFileFixture()], total: 1 });

    expect(component.files().length).toBe(1);
    expect(component.total()).toBe(1);
    expect(component.uploadSummary()).toContain("1");
    expect(component.isUploading()).toBe(false);
  });

  it("should show Polish quota error on upload failure", () => {
    component["handleFiles"]([createFile("x.py")]);

    const upload = httpTesting.expectOne(
      `${environment.apiUrl}/projects/${projectId}/upload`,
    );
    upload.flush(
      {
        type: "https://testgen.io/errors/quota-exceeded",
        title: "Quota Exceeded",
        status: 429,
        detail: "File size limit (100MB) exceeded for Basic plan",
      },
      { status: 429, statusText: "Too Many Requests" },
    );

    expect(component.uploadError()).toContain("Przekroczony limit");
    expect(component.isUploading()).toBe(false);
  });

  it("should keep the git form invalid for http URLs", () => {
    component.repoForm.controls.repoUrl.setValue("http://github.com/org/repo");
    expect(component.repoForm.controls.repoUrl.hasError("repoUrlScheme")).toBe(
      true,
    );
    expect(component.repoForm.valid).toBe(false);
  });

  it("should flag unsupported git hosts", () => {
    component.repoForm.controls.repoUrl.setValue(
      "https://evil.example.com/repo",
    );
    expect(component.repoForm.controls.repoUrl.hasError("repoUrlHost")).toBe(
      true,
    );
  });

  it("should accept valid github URL and POST on submit", () => {
    component.repoForm.controls.repoUrl.setValue(
      "https://github.com/org/repo.git",
    );
    component.repoForm.controls.branch.setValue("main");

    expect(component.repoForm.valid).toBe(true);

    component.onConnectRepo();

    const req = httpTesting.expectOne(
      `${environment.apiUrl}/projects/${projectId}/connect-repo`,
    );
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toEqual({
      repoUrl: "https://github.com/org/repo.git",
      branch: "main",
      authToken: null,
    });
    req.flush({
      projectId,
      repoUrl: "https://github.com/org/repo.git",
      branch: "main",
      filesIndexed: 4,
      message: "ok",
    });

    httpTesting.expectOne(listUrl).flush({ files: [], total: 0 });

    expect(component.repoMessage()).toContain("4");
    expect(component.isConnectingRepo()).toBe(false);
  });

  it("should expose a human-readable byte formatter", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
  });

  it("should request page 2 when the paginator moves forward", () => {
    component.onPageChange({
      pageIndex: 1,
      pageSize: 20,
      length: 606,
      previousPageIndex: 0,
    });

    const req = httpTesting.expectOne(
      `${environment.apiUrl}/projects/${projectId}/files?page=2&page_size=20`,
    );
    expect(req.request.method).toBe("GET");
    req.flush({ files: [], total: 606 });
    expect(component.page()).toBe(2);
    expect(component.pageSize()).toBe(20);
  });

  it("should request a larger page size when changed", () => {
    component.onPageChange({
      pageIndex: 0,
      pageSize: 100,
      length: 606,
      previousPageIndex: 0,
    });
    const req = httpTesting.expectOne(
      `${environment.apiUrl}/projects/${projectId}/files?page=1&page_size=100`,
    );
    req.flush({ files: [], total: 606 });
    expect(component.pageSize()).toBe(100);
  });

  it("should open the delete dialog and reload the list on confirm", () => {
    component.files.set([sourceFileFixture("f1", "a.py")]);
    component.total.set(1);
    fixture.detectChanges();

    const btn = fixture.nativeElement.querySelector(
      '[data-testid="delete-file"]',
    ) as HTMLButtonElement;
    expect(btn).toBeTruthy();

    dialogResult = true;
    btn.click();

    expect(matDialogOpen).toHaveBeenCalledTimes(1);
    // afterClosed(true) triggers a list reload (page 1).
    const reload = httpTesting.expectOne(listUrl);
    reload.flush({ files: [], total: 0 });
  });

  it("should not reload the list when the delete dialog is cancelled", () => {
    component.files.set([sourceFileFixture("f1", "a.py")]);
    component.total.set(1);
    fixture.detectChanges();

    const btn = fixture.nativeElement.querySelector(
      '[data-testid="delete-file"]',
    ) as HTMLButtonElement;
    dialogResult = false;
    btn.click();

    expect(matDialogOpen).toHaveBeenCalledTimes(1);
    httpTesting.expectNone(listUrl);
  });
});

describe("SourceFileDeleteDialogComponent", () => {
  let httpTesting: HttpTestingController;

  async function createDialog(fileId = "f1") {
    const dialogRef = { close: vi.fn() };
    await TestBed.configureTestingModule({
      imports: [SourceFileDeleteDialogComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: MatDialogRef, useValue: dialogRef },
        {
          provide: MAT_DIALOG_DATA,
          useValue: { fileId, filename: "a.py", projectId },
        },
      ],
    }).compileComponents();
    httpTesting = TestBed.inject(HttpTestingController);
    const dlgFixture = TestBed.createComponent(SourceFileDeleteDialogComponent);
    dlgFixture.detectChanges();
    return { dlgFixture, dialogRef };
  }

  afterEach(() => {
    httpTesting.verify();
  });

  it("calls DELETE and closes with true on confirm", async () => {
    const { dlgFixture, dialogRef } = await createDialog("f1");

    dlgFixture.componentInstance.onConfirm();

    const del = httpTesting.expectOne(
      `${environment.apiUrl}/projects/${projectId}/files/f1`,
    );
    expect(del.request.method).toBe("DELETE");
    del.flush(null, { status: 204, statusText: "No Content" });
    dlgFixture.detectChanges();

    expect(dialogRef.close).toHaveBeenCalledWith(true);
  });

  it("shows a role error and keeps the dialog open on 403", async () => {
    const { dlgFixture, dialogRef } = await createDialog("f1");

    dlgFixture.componentInstance.onConfirm();

    const del = httpTesting.expectOne(
      `${environment.apiUrl}/projects/${projectId}/files/f1`,
    );
    del.flush(
      { detail: "forbidden" },
      { status: 403, statusText: "Forbidden" },
    );
    dlgFixture.detectChanges();

    expect(dialogRef.close).not.toHaveBeenCalled();
    expect(dlgFixture.componentInstance.errorMessage()).toContain("Owner");
  });
});
