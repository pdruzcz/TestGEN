import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { provideRouter } from "@angular/router";

import { environment } from "../../../../environments/environment";
import { Transaction, TransactionList } from "../billing.service";
import { TransactionListComponent } from "./transaction-list.component";

const paidTxn: Transaction = {
  id: "txn-1",
  createdAt: "2026-09-10T14:32:00Z",
  amount: "50.00",
  currency: "PLN",
  status: "paid",
  paidAmount: "50.00",
  method: "card",
  transactionId: "ta_bKvkJX9Knk",
  orderId: "ord-1",
  invoiceId: "inv-1",
  invoiceNumber: "FV/2026/09/0003",
  testMode: false,
};

const pendingBlikTxn: Transaction = {
  id: "txn-2",
  createdAt: "2026-09-03T09:12:00Z",
  amount: "30.00",
  currency: "PLN",
  status: "pending",
  paidAmount: null,
  method: "blik",
  transactionId: "ta_m3RqpLw2xh",
  orderId: "ord-2",
  invoiceId: null,
  invoiceNumber: null,
  testMode: false,
};

const listBody: TransactionList = {
  items: [paidTxn, pendingBlikTxn],
  total: 23,
  page: 1,
  size: 20,
};

async function setup(): Promise<{
  fixture: ComponentFixture<TransactionListComponent>;
  httpMock: HttpTestingController;
}> {
  await TestBed.configureTestingModule({
    imports: [TransactionListComponent],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      NoopAnimationsModule,
      provideRouter([]),
    ],
  }).compileComponents();

  const fixture = TestBed.createComponent(TransactionListComponent);
  return { fixture, httpMock: TestBed.inject(HttpTestingController) };
}

describe("TransactionListComponent", () => {
  it("ładuje stronę 1 (20/stronę) i renderuje wiersze z kwotami i fakturą (AC2)", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/transactions?page=1&size=20`,
    );
    expect(req.request.method).toBe("GET");
    req.flush(listBody);
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("50,00 zł");
    expect(text).toContain("Karta");
    expect(text).toContain("BLIK");
    expect(text).toContain("Opłacona");
    expect(text).toContain("W toku");
    expect(text).toContain("FV/2026/09/0003");
    expect(text).toContain("Strona 1 z 2 — 23 transakcji");
    httpMock.verify();
  });

  it("filtry statusu i zakresu dat trafiają do query (snake_case)", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    httpMock
      .expectOne(`${environment.apiUrl}/billing/transactions?page=1&size=20`)
      .flush(listBody);
    fixture.detectChanges();

    fixture.componentInstance.statusFilter.set("paid");
    fixture.componentInstance.dateFrom.set("2026-09-01");
    fixture.componentInstance.dateTo.set("2026-09-30");
    fixture.componentInstance.applyFilters();
    fixture.detectChanges();

    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/transactions?page=1&size=20&status=paid&date_from=2026-09-01&date_to=2026-09-30`,
    );
    req.flush({ ...listBody, items: [paidTxn], total: 1 });
    fixture.detectChanges();

    expect(fixture.componentInstance.page()).toBe(1);
  });

  it("następna strona przechodzi na page=2 (AC2 — paginacja)", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    httpMock
      .expectOne(`${environment.apiUrl}/billing/transactions?page=1&size=20`)
      .flush(listBody);
    fixture.detectChanges();

    fixture.componentInstance.nextPage();
    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/transactions?page=2&size=20`,
    );
    req.flush({ ...listBody, page: 2 });
    fixture.detectChanges();

    expect(fixture.componentInstance.page()).toBe(2);
  });

  it("pusta lista pokazuje komunikat o braku transakcji", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    httpMock
      .expectOne(`${environment.apiUrl}/billing/transactions?page=1&size=20`)
      .flush({ items: [], total: 0, page: 1, size: 20 });
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Brak transakcji dla wybranych filtrów");
  });

  it("błąd pobrania pokazuje komunikat", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    httpMock
      .expectOne(`${environment.apiUrl}/billing/transactions?page=1&size=20`)
      .flush(null, { status: 500, statusText: "Server Error" });
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Nie udało się pobrać historii transakcji");
  });
});
