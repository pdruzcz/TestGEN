import { ComponentRef } from "@angular/core";
import { TestBed } from "@angular/core/testing";
import {
  ActivatedRoute,
  convertToParamMap,
  provideRouter,
} from "@angular/router";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { MatDialog } from "@angular/material/dialog";
import { of, throwError } from "rxjs";
import { vi } from "vitest";

import { DocumentUploadComponent } from "./document-upload.component";
import { DocumentService } from "../services/document.service";
import type { DocumentFile } from "../services/document.service";

const projectId = "proj-123";

/** A classified, ready document as the backend (post snake-case transform)
 * would return it. */
function classifiedDoc(over: Partial<DocumentFile> = {}): DocumentFile {
  return {
    id: "doc-1",
    projectId,
    filename: "api.pdf",
    fileSize: 1024,
    fileCategory: "documentation",
    docFormat: "pdf",
    pageCount: 3,
    createdAt: "2026-06-17T00:00:00.000Z",
    isCleanedUp: false,
    processingStatus: "ready",
    errorMessage: null,
    docType: "opis_api",
    classificationConfidence: 92,
    classificationJustification: "Endpointy REST",
    ...over,
  };
}

function mockMatDialog() {
  return {
    open: vi.fn().mockReturnValue({ afterClosed: () => of(false) }),
  };
}

describe("DocumentUploadComponent (classification — Story 2.3)", () => {
  let component: DocumentUploadComponent;
  let docService: {
    listDocuments: ReturnType<typeof vi.fn>;
    classifyDocument: ReturnType<typeof vi.fn>;
    reanalyzeDocument: ReturnType<typeof vi.fn>;
    uploadDocuments: ReturnType<typeof vi.fn>;
    getTaskStatus: ReturnType<typeof vi.fn>;
  };

  function setup(documents: DocumentFile[]) {
    docService = {
      listDocuments: vi
        .fn()
        .mockReturnValue(of({ documents, total: documents.length })),
      classifyDocument: vi.fn().mockReturnValue(of({})),
      reanalyzeDocument: vi.fn().mockReturnValue(of({})),
      uploadDocuments: vi.fn(),
      getTaskStatus: vi.fn(),
    };

    TestBed.configureTestingModule({
      imports: [DocumentUploadComponent, NoopAnimationsModule],
      providers: [
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: { paramMap: convertToParamMap({ projectId }) },
          },
        },
        { provide: DocumentService, useValue: docService },
        { provide: MatDialog, useValue: mockMatDialog() },
      ],
    });

    const fixture = TestBed.createComponent(DocumentUploadComponent);
    component = fixture.componentInstance;
    fixture.detectChanges(); // triggers ngOnInit → loadDocuments()
    return fixture;
  }

  it("renders the doc-type chip with a PL label when classified (AC7)", () => {
    const fixture = setup([classifiedDoc()]);
    const chip = fixture.nativeElement.querySelector(".doc-type-chip");

    expect(chip).toBeTruthy();
    expect(chip.textContent).toContain("Opis API");
  });

  it("tooltip includes the confidence percentage (AC7)", () => {
    setup([classifiedDoc({ classificationConfidence: 87 })]);

    const tooltip = component.classificationTooltip(
      component.uploadedDocuments()[0] as never,
    );
    expect(tooltip).toContain("87%");
  });

  it("hides the chip when no doc_type is set", () => {
    const fixture = setup([classifiedDoc({ docType: null })]);
    const chip = fixture.nativeElement.querySelector(".doc-type-chip");

    expect(chip).toBeFalsy();
  });

  it("re-classifies on button click and refreshes the list (AC7)", () => {
    const fixture = setup([classifiedDoc()]);
    // loadDocuments was already called once on init
    expect(docService.listDocuments).toHaveBeenCalledTimes(1);

    const btn = fixture.nativeElement.querySelector(
      'button[aria-label="Klasyfikuj ponownie"]',
    ) as HTMLButtonElement;
    expect(btn).toBeTruthy();

    btn.click();

    // classifyDocument called with the doc id (no engine-mode argument)
    expect(docService.classifyDocument).toHaveBeenCalledTimes(1);
    expect(docService.classifyDocument).toHaveBeenCalledWith("doc-1");
    // success → list reloaded
    expect(docService.listDocuments).toHaveBeenCalledTimes(2);
  });

  it("maps all six backend doc_types to labels", () => {
    setup([]);
    expect(component.docTypeLabel("specyfikacja_wymagań")).toBe(
      "Specyfikacja wymagań",
    );
    expect(component.docTypeLabel("podręcznik_użytkownika")).toBe(
      "Podręcznik użytkownika",
    );
    expect(component.docTypeLabel("instrukcja_techniczna")).toBe(
      "Instrukcja techniczna",
    );
    expect(component.docTypeLabel("opis_api")).toBe("Opis API");
    expect(component.docTypeLabel("notatki_projektowe")).toBe(
      "Notatki projektowe",
    );
    expect(component.docTypeLabel("inny")).toBe("Inny");
  });

  it("re-analyzes ready/failed docs via reanalyzeDocument (not /analyze)", () => {
    setup([
      classifiedDoc({ id: "doc-ready" }),
      classifiedDoc({
        id: "doc-failed",
        processingStatus: "failed",
        errorMessage: "boom",
      }),
    ]);

    component.startAnalysis();

    // Both ready + failed are re-analyzed, via the document reparse endpoint.
    expect(docService.reanalyzeDocument).toHaveBeenCalledTimes(2);
    expect(docService.reanalyzeDocument).toHaveBeenCalledWith("doc-ready");
    expect(docService.reanalyzeDocument).toHaveBeenCalledWith("doc-failed");
    expect(component.isAnalyzing()).toBe(false);
  });

  it("shows a clear PL quota message on 429 (not raw HTTP text)", () => {
    setup([classifiedDoc()]);
    docService.reanalyzeDocument = vi.fn(() =>
      throwError(() => ({
        status: 429,
        error: {
          type: "https://testgen.io/errors/quota-exceeded",
          plan: "basic",
          limit: 10,
        },
      })),
    );

    component.startAnalysis();

    const msg = component.uploadError();
    expect(msg).toContain("miesięczny limit analiz");
    expect(msg).toContain("basic");
    expect(msg).toContain("10");
    expect(msg).not.toContain("Http failure");
    expect(component.isAnalyzing()).toBe(false);
  });
});
