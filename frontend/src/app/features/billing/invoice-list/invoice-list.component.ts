import { Component, OnInit, inject, signal } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatIcon } from "@angular/material/icon";
import { RouterLink } from "@angular/router";

import {
  BillingService,
  Invoice,
  InvoicePaymentMethod,
  InvoiceStatus,
} from "../billing.service";

/** Rozmiar strony listy faktur (7.6 AC5 — domyślnie 20). */
export const INVOICE_PAGE_SIZE = 20;

/**
 * Lista faktur VAT (Story 7.6, AC5) — numer, data, kwota, status, pobranie
 * PDF z MinIO. PDF generuje się asynchronicznie po płatności (Celery) —
 * wiersz z niedostępnym PDF pokazuje status „w przygotowaniu".
 */
@Component({
  selector: "app-invoice-list",
  imports: [MatCardModule, MatButtonModule, MatIcon, RouterLink],
  templateUrl: "./invoice-list.component.html",
  styleUrl: "./invoice-list.component.scss",
  providers: [BillingService],
})
export class InvoiceListComponent implements OnInit {
  private readonly billing = inject(BillingService);

  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly actionError = signal<string | null>(null);
  readonly invoices = signal<Invoice[]>([]);
  readonly page = signal(1);
  readonly total = signal(0);
  readonly downloadingId = signal<string | null>(null);

  readonly pageSize = INVOICE_PAGE_SIZE;

  ngOnInit(): void {
    this.load();
  }

  /** AC5 — strona listy malejąco po dacie wystawienia. */
  load(page = this.page()): void {
    this.error.set(null);
    this.billing.getInvoices(page, this.pageSize).subscribe({
      next: (list) => {
        this.invoices.set(list.items);
        this.page.set(list.page);
        this.total.set(list.total);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.listErrorMessage(err?.status));
        this.loading.set(false);
      },
    });
  }

  nextPage(): void {
    if (this.hasNextPage()) {
      this.load(this.page() + 1);
    }
  }

  prevPage(): void {
    if (this.page() > 1) {
      this.load(this.page() - 1);
    }
  }

  hasNextPage(): boolean {
    return this.page() * this.pageSize < this.total();
  }

  totalPages(): number {
    return Math.max(1, Math.ceil(this.total() / this.pageSize));
  }

  /** AC5 — pobranie PDF (blob → download); 404 = PDF jeszcze w generowaniu. */
  downloadPdf(invoice: Invoice): void {
    this.actionError.set(null);
    this.downloadingId.set(invoice.id);
    this.billing.getInvoicePdf(invoice.id).subscribe({
      next: (blob) => {
        this.triggerDownload(blob, this.pdfFilename(invoice.invoiceNumber));
        this.downloadingId.set(null);
      },
      error: (err) => {
        this.downloadingId.set(null);
        this.actionError.set(
          err?.status === 404
            ? "PDF tej faktury jeszcze się generuje — odśwież listę za chwilę."
            : "Nie udało się pobrać PDF faktury. Spróbuj ponownie za chwilę.",
        );
      },
    });
  }

  statusLabel(status: InvoiceStatus): string {
    switch (status) {
      case "issued":
        return "Wystawiona";
      case "canceled":
        return "Anulowana";
      case "corrected":
        return "Skorygowana";
      default:
        return status;
    }
  }

  methodLabel(method: InvoicePaymentMethod): string {
    switch (method) {
      case "card":
        return "Karta";
      case "blik":
        return "BLIK";
      case "bank_transfer":
        return "Przelew";
      default:
        return method;
    }
  }

  /** Kwota brutto z walutą — „50,00 zł" (backend wysyła „50.00"/„PLN"). */
  amountLabel(invoice: Invoice): string {
    const gross = invoice.totalGross.replace(".", ",");
    const currency = invoice.currency === "PLN" ? "zł" : ` ${invoice.currency}`;
    return `${gross} ${currency}`.trim();
  }

  pdfFilename(invoiceNumber: string): string {
    return `Faktura_${invoiceNumber.replaceAll("/", "_")}.pdf`;
  }

  /** Blob → zapis pliku (publiczny: testowalny przez spy na URL.createObjectURL). */
  triggerDownload(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  private listErrorMessage(status: number | undefined): string {
    if (status === 403) {
      return "Brak dostępu do faktur tego konta.";
    }
    return "Nie udało się pobrać listy faktur. Spróbuj ponownie za chwilę.";
  }
}
