import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { provideRouter } from "@angular/router";

import { environment } from "../../../../environments/environment";
import { Invoice, InvoiceList } from "../billing.service";
import {
  INVOICE_PAGE_SIZE,
  InvoiceListComponent,
} from "./invoice-list.component";

const mockInvoices: Invoice[] = [
  {
    id: "inv-1",
    invoiceNumber: "FV/2026/09/0003",
    issueDate: "2026-09-10",
    saleDate: "2026-09-10",
    buyerName: "Nexio Management Sp. z o.o.",
    subtotalNet: "40.65",
    vatRate: "23",
    vatAmount: "9.35",
    totalGross: "50.00",
    currency: "PLN",
    paymentMethod: "card",
    status: "issued",
    pdfAvailable: true,
    createdAt: "2026-09-10T12:00:00Z",
  },
  {
    id: "inv-2",
    invoiceNumber: "FV/2026/09/0002",
    issueDate: "2026-09-03",
    saleDate: "2026-09-03",
    buyerName: "Nexio Management Sp. z o.o.",
    subtotalNet: "24.39",
    vatRate: "23",
    vatAmount: "5.61",
    totalGross: "30.00",
    currency: "PLN",
    paymentMethod: "blik",
    status: "issued",
    pdfAvailable: false,
    createdAt: "2026-09-03T12:00:00Z",
  },
  {
    id: "inv-3",
    invoiceNumber: "FV/2026/08/0001",
    issueDate: "2026-08-05",
    saleDate: "2026-08-05",
    buyerName: "Nexio Management Sp. z o.o.",
    subtotalNet: "10.49",
    vatRate: "23",
    vatAmount: "2.41",
    totalGross: "12.90",
    currency: "PLN",
    paymentMethod: "bank_transfer",
    status: "corrected",
    pdfAvailable: true,
    createdAt: "2026-08-05T12:00:00Z",
  },
];

const mockList: InvoiceList = {
  items: mockInvoices,
  total: 3,
  page: 1,
  size: INVOICE_PAGE_SIZE,
};

describe("InvoiceListComponent (Story 7.6, AC5)", () => {
  let fixture: ComponentFixture<InvoiceListComponent>;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [InvoiceListComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        NoopAnimationsModule,
      ],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(InvoiceListComponent);
    fixture.detectChanges();
  });

  function flushList(list: InvoiceList = mockList): void {
    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/invoices?page=1&size=${INVOICE_PAGE_SIZE}`,
    );
    req.flush(list);
    fixture.detectChanges();
  }

  it("GET /billing/invoices — tabela z numerami, kwotami i statusami (AC5)", () => {
    flushList();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("FV/2026/09/0003");
    expect(text).toContain("50,00 zł");
    expect(text).toContain("Karta");
    expect(text).toContain("BLIK");
    expect(text).toContain("Wystawiona");
    expect(text).toContain("Skorygowana");
    httpMock.verify();
  });

  it("PDF w generowaniu — chip W-toku bez przycisku pobrania", () => {
    flushList();

    const rows = fixture.nativeElement.querySelectorAll("tbody tr");
    expect(rows.length).toBe(3);
    const pendingRow = rows[1] as HTMLElement; // inv-2: pdfAvailable=false
    expect(pendingRow.textContent).toContain("W toku");
    expect(
      pendingRow.querySelector("button[aria-label*='Pobierz']"),
    ).toBeNull();
  });

  it("pobranie PDF — blob + nazwa pliku z numerem faktury (AC5)", () => {
    flushList();
    const downloadSpy = vi.spyOn(fixture.componentInstance, "triggerDownload");

    fixture.componentInstance.downloadPdf(mockInvoices[0]);
    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/invoices/inv-1/pdf`,
    );
    expect(req.request.method).toBe("GET");
    req.flush(new Blob(["%PDF"], { type: "application/pdf" }));
    fixture.detectChanges();

    expect(downloadSpy).toHaveBeenCalledWith(
      expect.any(Blob),
      "Faktura_FV_2026_09_0003.pdf",
    );
    httpMock.verify();
  });

  it("404 na PDF — komunikat o trwającym generowaniu", () => {
    flushList();

    fixture.componentInstance.downloadPdf(mockInvoices[0]);
    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/invoices/inv-1/pdf`,
    );
    req.flush(null, { status: 404, statusText: "Not Found" });
    fixture.detectChanges();

    expect(fixture.componentInstance.actionError()).toContain(
      "jeszcze się generuje",
    );
  });

  it("paginacja — następna strona wysyła page=2 (AC5)", () => {
    flushList({
      ...mockList,
      items: mockInvoices.slice(0, 1),
      total: 25,
      page: 1,
    });

    fixture.componentInstance.nextPage();
    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/invoices?page=2&size=${INVOICE_PAGE_SIZE}`,
    );
    req.flush({
      items: mockInvoices,
      total: 25,
      page: 2,
      size: INVOICE_PAGE_SIZE,
    });
    fixture.detectChanges();

    expect(fixture.componentInstance.page()).toBe(2);
    expect(fixture.componentInstance.totalPages()).toBe(2);
  });

  it("brak faktur — stan pusty", () => {
    flushList({ items: [], total: 0, page: 1, size: INVOICE_PAGE_SIZE });

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Brak faktur");
  });

  it("błąd listy — komunikat i powrót do planów", () => {
    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/invoices?page=1&size=${INVOICE_PAGE_SIZE}`,
    );
    req.flush("Forbidden", { status: 403, statusText: "Forbidden" });
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Brak dostępu do faktur");
    expect(text).toContain("Wróć do planów");
  });
});
