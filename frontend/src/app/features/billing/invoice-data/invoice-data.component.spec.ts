import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { provideRouter } from "@angular/router";

import { environment } from "../../../../environments/environment";
import { InvoiceData } from "../billing.service";
import { InvoiceDataComponent } from "./invoice-data.component";

const mockData: InvoiceData = {
  companyName: "Nexio Management Sp. z o.o.",
  nip: "5213000000",
  address: {
    street: "ul. Przykładowa 12/3",
    city: "Warszawa",
    postalCode: "00-001",
    country: "Polska",
  },
};

describe("InvoiceDataComponent (Story 7.6, AC4)", () => {
  let fixture: ComponentFixture<InvoiceDataComponent>;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [InvoiceDataComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        NoopAnimationsModule,
      ],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(InvoiceDataComponent);
    fixture.detectChanges();
  });

  function flushData(data: InvoiceData = mockData): void {
    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/invoice-data`,
    );
    req.flush(data);
    fixture.detectChanges();
  }

  it("GET /billing/invoice-data — formularz wypełniony danymi (AC4)", () => {
    flushData();

    const form = fixture.componentInstance.form;
    expect(form.getRawValue().companyName).toBe(mockData.companyName);
    expect(form.getRawValue().nip).toBe(mockData.nip);
    expect(form.getRawValue().street).toBe(mockData.address.street);
    expect(form.getRawValue().city).toBe(mockData.address.city);
    expect(form.getRawValue().postalCode).toBe(mockData.address.postalCode);
    httpMock.verify();
  });

  it("PUT /billing/invoice-data — payload z płaskiego formularza (AC4)", () => {
    flushData();

    fixture.componentInstance.save();
    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/invoice-data`,
    );
    expect(req.request.method).toBe("PUT");
    expect(req.request.body).toEqual(mockData);
    req.flush(mockData);
    fixture.detectChanges();

    expect(fixture.componentInstance.saved()).toBe(true);
    httpMock.verify();
  });

  it("pusta nazwa firmy — walidacja wymagana, bez PUT", () => {
    flushData();
    fixture.componentInstance.form.controls.companyName.setValue("");

    fixture.componentInstance.save();

    expect(fixture.componentInstance.form.controls.companyName.invalid).toBe(
      true,
    );
    httpMock.expectNone(`${environment.apiUrl}/billing/invoice-data`);
  });

  it("403 przy zapisie — komunikat o roli Ownera", () => {
    flushData();

    fixture.componentInstance.save();
    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/invoice-data`,
    );
    req.flush("Forbidden", { status: 403, statusText: "Forbidden" });
    fixture.detectChanges();

    expect(fixture.componentInstance.actionError()).toContain("Owner");
  });

  it("null NIP — wysyłany jako null, nie pusty string (AC4)", () => {
    flushData({ ...mockData, nip: null });
    fixture.componentInstance.save();

    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/invoice-data`,
    );
    expect(req.request.body.nip).toBeNull();
    req.flush(mockData);
  });
});
