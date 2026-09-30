import { Component, OnInit, inject, signal } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatIcon } from "@angular/material/icon";
import { MatSelectModule } from "@angular/material/select";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { FormsModule } from "@angular/forms";
import { RouterLink } from "@angular/router";

import {
  BillingService,
  PaymentStatus,
  Transaction,
  TransactionMethod,
} from "../billing.service";

/** Rozmiar strony historii transakcji (7.7 AC2). */
export const TRANSACTION_PAGE_SIZE = 20;

/**
 * Historia transakcji (Story 7.7, AC2) — wszystkie płatności konta malejąco
 * po dacie: kwota, metoda (z faktury / BLIK z aliasu), status, powiązana
 * faktura. Filtry: status + zakres dat; paginacja 20/stronę. Dostępna dla
 * Ownera i Usera (przeglądanie).
 */
@Component({
  selector: "app-transaction-list",
  imports: [
    MatCardModule,
    MatButtonModule,
    MatIcon,
    MatSelectModule,
    MatFormFieldModule,
    MatInputModule,
    FormsModule,
    RouterLink,
  ],
  templateUrl: "./transaction-list.component.html",
  styleUrl: "./transaction-list.component.scss",
  providers: [BillingService],
})
export class TransactionListComponent implements OnInit {
  private readonly billing = inject(BillingService);

  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly transactions = signal<Transaction[]>([]);
  readonly page = signal(1);
  readonly total = signal(0);

  readonly pageSize = TRANSACTION_PAGE_SIZE;

  /** AC2 — filtry; puste = brak filtru (wszystkie statusy/daty). */
  readonly statusFilter = signal<"" | PaymentStatus>("");
  readonly dateFrom = signal("");
  readonly dateTo = signal("");

  readonly statusOptions: { value: "" | PaymentStatus; label: string }[] = [
    { value: "", label: "Wszystkie" },
    { value: "paid", label: "Opłacone" },
    { value: "pending", label: "W toku" },
    { value: "charged_back", label: "Chargeback" },
    { value: "refunded", label: "Zwrócone" },
  ];

  ngOnInit(): void {
    this.load();
  }

  /** AC2 — strona listy malejąco po dacie, z aktywnymi filtrami. */
  load(page = this.page()): void {
    this.error.set(null);
    this.billing
      .getTransactions(page, this.pageSize, {
        status: this.statusFilter() || undefined,
        dateFrom: this.dateFrom() || undefined,
        dateTo: this.dateTo() || undefined,
      })
      .subscribe({
        next: (list) => {
          this.transactions.set(list.items);
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

  /** Zastosowanie filtrów wraca na pierwszą stronę wyników. */
  applyFilters(): void {
    this.loading.set(true);
    this.load(1);
  }

  clearFilters(): void {
    this.statusFilter.set("");
    this.dateFrom.set("");
    this.dateTo.set("");
    this.applyFilters();
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

  dateLabel(value: string): string {
    return new Date(value).toLocaleDateString("pl-PL");
  }

  statusLabel(status: PaymentStatus): string {
    switch (status) {
      case "paid":
        return "Opłacona";
      case "pending":
        return "W toku";
      case "charged_back":
        return "Chargeback";
      case "refunded":
        return "Zwrócona";
      default:
        return status;
    }
  }

  methodLabel(method: TransactionMethod | null): string {
    if (method === null) {
      return "—";
    }
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

  /** Kwota — „50,00 zł" (backend wysyła „50.00"/„PLN"). */
  amountLabel(transaction: Transaction): string {
    const amount = transaction.amount.replace(".", ",");
    const currency =
      transaction.currency === "PLN" ? "zł" : ` ${transaction.currency}`;
    return `${amount} ${currency}`.trim();
  }

  private listErrorMessage(status: number | undefined): string {
    if (status === 403) {
      return "Brak dostępu do historii transakcji tego konta.";
    }
    return "Nie udało się pobrać historii transakcji. Spróbuj ponownie za chwilę.";
  }
}
