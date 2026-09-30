import { HttpClient } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import { Observable } from "rxjs";

import { environment } from "../../../environments/environment";

/** Nazwa planu — model 3-planowy (CR#2 2026-08-28). */
export type PlanName = "freemium" | "basic" | "premium";

/** Macierz limitów planu (JSONB `features` z backendu — jedno źródło prawdy). */
export interface PlanFeatures {
  analyses: number | null;
  testCases: number | null;
  storageBytes: number | null;
  filesPerAnalysis: number | null;
  rateLimitPerMin: number | null;
  prioritySupport?: boolean;
  llmCostTracking?: boolean;
  gatedModules?: Record<string, PlanName>;
  [key: string]: unknown;
}

export interface Plan {
  id: string;
  name: PlanName;
  displayName: string;
  priceMonthly: string;
  currency: string;
  features: PlanFeatures;
  isActive: boolean;
  sortOrder: number;
}

export interface PlanComparison {
  plans: Plan[];
  currentPlan: PlanName | null;
  /** URL-e dokumentów prawnych z konfiguracji backendu (wymóg tpay). */
  termsUrl: string;
  privacyPolicyUrl: string;
}

export interface Subscription {
  id: string;
  tenantId: string;
  planId: string;
  status: "active" | "past_due" | "canceled" | "incomplete";
  currentPeriodStart: string;
  currentPeriodEnd: string;
  nextChargeAt: string | null;
  cancelAtPeriodEnd: boolean;
  trialEnd: string | null;
}

/** Aktywna metoda płatności subskrypcji w detailu (Story 7.7, AC3). */
export interface SubscriptionPaymentMethod {
  kind: PaymentMethodKind;
  cardTail: string | null;
  cardBrand: string | null;
  tpayStatus: PaymentMethodStatus;
  isDefault: boolean;
}

/** GET /billing/subscription (7.7 AC3) — detail portalu (nadzbiór Subscription). */
export interface SubscriptionDetail extends Subscription {
  planName: PlanName | null;
  planDisplayName: string | null;
  planPriceMonthly: string | null;
  planCurrency: string | null;
  paymentMethod: SubscriptionPaymentMethod | null;
  /** Zaplanowany downgrade (7.5) — jego plan docelowy obowiązuje na końcu okresu. */
  pendingChange: PlanChange | null;
  graceUntil: string | null;
}

/** Klucze zasobów po konwersji snake_case → camelCase (snakeCaseInterceptor). */
export type UsageResource =
  | "analyses"
  | "testCases"
  | "storageBytes"
  | "filesPerAnalysis";

/** Zużycie zasobu (Story 7.8) — limit/percent = null → unlimited. */
export interface UsageEntry {
  used: number;
  limit: number | null;
  percent: number | null;
}

export type Usage = Partial<Record<UsageResource, UsageEntry>>;

/** Karta zasobu na dashboardzie zużycia (Story 7.9, AC1); limit/percentage null → unlimited. */
export interface UsageDashboardCounter {
  type: UsageResource;
  value: number;
  limit: number | null;
  percentage: number | null;
}

/** Prognoza osiągnięcia limitu analiz (Story 7.9, AC4) — opcjonalna. */
export interface UsageForecast {
  counterType: UsageResource;
  limitDate: string;
  avgDaily: number;
  daysToLimit: number;
  exceedsBeforePeriodEnd: boolean;
}

/** Odpowiedź GET /billing/usage/dashboard (Story 7.9, AC5). */
export interface UsageDashboard {
  currentPeriod: { start: string; end: string };
  plan: string | null;
  counters: UsageDashboardCounter[];
  forecast: UsageForecast | null;
  daysRemaining: number;
}

/** Punkt wykresu historii zużycia (Story 7.9, AC3) — skumulowana wartość na dzień. */
export interface UsageHistoryPoint {
  date: string;
  value: number;
}

/** Odpowiedź GET /billing/usage/history (Story 7.9, AC3). */
export interface UsageHistory {
  counterType: UsageResource;
  days: number;
  points: UsageHistoryPoint[];
}

/** Plan płatny podlegający zakupowi (Freemium nie podlega — jedyny cykl: miesięczny). */
export type PaidPlan = "basic" | "premium";

/** Odpowiedź POST /billing/checkout (Story 7.4, AC1) — URL Panelu Transakcyjnego tpay. */
export interface CheckoutResponse {
  orderId: string;
  transactionId: string;
  transactionPaymentUrl: string;
  plan: PaidPlan;
  amount: string;
  currency: string;
}

export type PaymentStatus = "pending" | "paid" | "charged_back" | "refunded";

/** Status transakcji — polling stron powrotu (AC2) + fallback reconciliation (AC7). */
export interface TransactionStatusResponse {
  orderId: string;
  status: PaymentStatus;
  plan: PlanName | null;
  amount: string;
  currency: string;
  testMode: boolean;
}

/** Rodzaj zapisanej metody płatności (Story 7.2, AC3). */
export type PaymentMethodKind =
  | "card_token"
  | "blik_alias_uid"
  | "blik_alias_payid";

/** Status metody u tpay + stan lokalnej rejestracji (pending = rejestracja w toku). */
export type PaymentMethodStatus =
  | "pending"
  | "active"
  | "suspended"
  | "deleted";

/** Pozycja listy GET /billing/payment-methods (AC3). */
export interface PaymentMethod {
  id: string;
  kind: PaymentMethodKind;
  cardTail: string | null;
  cardBrand: string | null;
  tpayStatus: PaymentMethodStatus;
  isDefault: boolean;
  createdAt: string;
}

/** Odpowiedź POST /billing/payment-methods — URL rejestracji karty u tpay (AC2). */
export interface PaymentMethodRegistration {
  tokenId: string;
  registrationUrl: string;
}

/** Podgląd proration (Story 7.5, AC5) — kwota liczona lokalnie na backendzie. */
export interface Proration {
  amount: string;
  periodDays: number;
  remainingDays: number;
  currentPlan: PlanName;
  newPlan: PlanName;
  currentPrice: string;
  newPrice: string;
  fullPrice: string;
  changeType: "upgrade" | "downgrade";
  currency: string;
  nextChargeAt: string | null;
}

/** Rekord historii zmiany planu (Story 7.5, AC4). */
export interface PlanChange {
  id: string;
  fromPlan: PlanName;
  toPlan: PlanName;
  changeType: "upgrade" | "downgrade";
  status: "pending" | "completed" | "canceled";
  requestedAt: string;
  effectiveAt: string | null;
  prorationDetails: Record<string, unknown>;
}

/** Odpowiedź POST /billing/subscription/change (Story 7.5, AC1/AC2). */
export interface PlanChangeResult {
  change: PlanChange;
  changeType: "upgrade" | "downgrade";
  amount: string;
  currency: string;
  paymentRequired: boolean;
  /** URL checkoutu tpay — tylko upgrade bez zapisanej metody płatności. */
  paymentUrl: string | null;
  orderId: string | null;
}

/** Status faktury VAT (7.6); `corrected` — scope przyszły (faktury korygujące). */
export type InvoiceStatus = "issued" | "canceled" | "corrected";

/** Metoda płatności fakturem (7.6 AC1). */
export type InvoicePaymentMethod = "card" | "bank_transfer" | "blik";

/** Pozycja listy GET /billing/invoices (7.6 AC5) — numer, data, kwota, status. */
export interface Invoice {
  id: string;
  invoiceNumber: string;
  issueDate: string;
  saleDate: string;
  buyerName: string;
  subtotalNet: string;
  vatRate: string;
  vatAmount: string;
  totalGross: string;
  currency: string;
  paymentMethod: InvoicePaymentMethod;
  status: InvoiceStatus;
  /** false → PDF jeszcze generowany asynchronicznie (Celery). */
  pdfAvailable: boolean;
  createdAt: string;
}

/** Strona listy faktur (7.6 AC5) — domyślnie 20/stronę, malejąco po dacie. */
export interface InvoiceList {
  items: Invoice[];
  total: number;
  page: number;
  size: number;
}

/** Metoda płatności transakcji (7.7 AC2) — z faktury albo BLIK z aliasu; null = nieznana. */
export type TransactionMethod = "card" | "blik" | "bank_transfer";

/** Pozycja listy GET /billing/transactions (7.7 AC2). */
export interface Transaction {
  id: string;
  createdAt: string;
  amount: string;
  currency: string;
  status: PaymentStatus;
  paidAmount: string | null;
  method: TransactionMethod | null;
  /** Identyfikator u tpay (wsparcie BOK) — nullable przed odpowiedzią providera. */
  transactionId: string | null;
  orderId: string | null;
  invoiceId: string | null;
  invoiceNumber: string | null;
  testMode: boolean;
}

/** Filtry historii transakcji (7.7 AC2) — status + zakres dat. */
export interface TransactionFilters {
  status?: PaymentStatus;
  dateFrom?: string;
  dateTo?: string;
}

/** Strona listy transakcji (7.7 AC2) — domyślnie 20/stronę, malejąco po dacie. */
export interface TransactionList {
  items: Transaction[];
  total: number;
  page: number;
  size: number;
}

/** Adres danej fakturowej (JSONB; klucze po konwersji snake_case → camelCase). */
export interface InvoiceAddress {
  street?: string;
  city?: string;
  postalCode?: string;
  country?: string;
}

/** Dane fakturowe tenanta (7.6 AC4) — snapshot do faktury przy wystawieniu. */
export interface InvoiceData {
  companyName: string;
  nip: string | null;
  address: InvoiceAddress;
}

/** Serwis HTTP modułu billing (Story 7.1 + 7.4 + 7.2 + 7.5 + 7.6). */
@Injectable()
export class BillingService {
  private readonly apiUrl = environment.apiUrl;
  private readonly http = inject(HttpClient);

  /** Porównanie planów + aktualny plan tenanta + linki prawne. */
  getPlans(): Observable<PlanComparison> {
    return this.http.get<PlanComparison>(`${this.apiUrl}/billing/plans`);
  }

  /** Detail subskrypcji tenanta (7.7 AC3) — plan, metoda płatności, downgrade. */
  getSubscription(): Observable<SubscriptionDetail> {
    return this.http.get<SubscriptionDetail>(
      `${this.apiUrl}/billing/subscription`,
    );
  }

  /** Anulowanie subskrypcji (7.7 AC4) — lokalnie, aktywna do końca okresu. */
  cancelSubscription(): Observable<SubscriptionDetail> {
    return this.http.post<SubscriptionDetail>(
      `${this.apiUrl}/billing/subscription/cancel`,
      {},
    );
  }

  /** Reaktywacja anulowanej subskrypcji (7.7 AC5) — bez przerwy w odnowieniach. */
  reactivateSubscription(): Observable<SubscriptionDetail> {
    return this.http.post<SubscriptionDetail>(
      `${this.apiUrl}/billing/subscription/reactivate`,
      {},
    );
  }

  /** Historia transakcji (7.7 AC2) — filtry statusu/zakresu dat + paginacja. */
  getTransactions(
    page = 1,
    size = 20,
    filters: TransactionFilters = {},
  ): Observable<TransactionList> {
    // Interceptor zamienia tylko body — parametry jawnie w snake_case.
    const params: Record<string, string> = {
      page: String(page),
      size: String(size),
    };
    if (filters.status) {
      params["status"] = filters.status;
    }
    if (filters.dateFrom) {
      params["date_from"] = filters.dateFrom;
    }
    if (filters.dateTo) {
      params["date_to"] = filters.dateTo;
    }
    return this.http.get<TransactionList>(
      `${this.apiUrl}/billing/transactions`,
      { params },
    );
  }

  /** Liczniki użycia tenanta z limitami planu i procentem (Story 7.8). */
  getUsage(): Observable<Usage> {
    return this.http.get<Usage>(`${this.apiUrl}/billing/usage`);
  }

  /** Dane dashboardu zużycia (Story 7.9, AC5): okres, plan, karty, prognoza. */
  getUsageDashboard(): Observable<UsageDashboard> {
    return this.http.get<UsageDashboard>(
      `${this.apiUrl}/billing/usage/dashboard`,
    );
  }

  /** Historia zużycia zasobu do wykresu (Story 7.9, AC3) — daily snapshoty. */
  getUsageHistory(
    counterType: UsageResource,
    days = 30,
  ): Observable<UsageHistory> {
    return this.http.get<UsageHistory>(
      `${this.apiUrl}/billing/usage/history`,
      // Interceptor zamienia tylko body — parametry jawnie w snake_case.
      { params: { counter_type: counterType, days } },
    );
  }

  /** Inicjacja checkoutu tpay (AC1) — jedyny cykl: miesięczny. */
  createCheckout(plan: PaidPlan): Observable<CheckoutResponse> {
    return this.http.post<CheckoutResponse>(`${this.apiUrl}/billing/checkout`, {
      plan,
    });
  }

  /** Status transakcji po order_id (AC2/AC7) — polling stron powrotu. */
  getTransactionStatus(orderId: string): Observable<TransactionStatusResponse> {
    return this.http.get<TransactionStatusResponse>(
      `${this.apiUrl}/billing/transactions/${orderId}`,
    );
  }

  /** Metody płatności tenanta (7.2 AC3) — karty i aliasy BLIK. */
  getPaymentMethods(): Observable<PaymentMethod[]> {
    return this.http.get<PaymentMethod[]>(
      `${this.apiUrl}/billing/payment-methods`,
    );
  }

  /** Dodaj kartę — rejestracja bez obciążenia (7.2 AC2), redirect na tpay. */
  addPaymentMethod(): Observable<PaymentMethodRegistration> {
    return this.http.post<PaymentMethodRegistration>(
      `${this.apiUrl}/billing/payment-methods`,
      {},
    );
  }

  /** Usunięcie metody (7.2 AC3) — 409 gdy to ostatnia metoda aktywnej subskrypcji. */
  deletePaymentMethod(id: string): Observable<PaymentMethod> {
    return this.http.delete<PaymentMethod>(
      `${this.apiUrl}/billing/payment-methods/${id}`,
    );
  }

  /** Zmiana planu (7.5 AC1/AC2) — upgrade prorated / downgrade na koniec okresu. */
  changePlan(plan: PlanName): Observable<PlanChangeResult> {
    return this.http.post<PlanChangeResult>(
      `${this.apiUrl}/billing/subscription/change`,
      { plan },
    );
  }

  /** Rezygnacja z zaplanowanego downgrade (7.5 AC3) — bez wywołań tpay. */
  cancelPendingChange(): Observable<PlanChange> {
    return this.http.post<PlanChange>(
      `${this.apiUrl}/billing/subscription/change/cancel-pending`,
      {},
    );
  }

  /** Historia zmian planu tenanta (7.5 AC4) — najnowsze pierwsze. */
  getChangeHistory(): Observable<PlanChange[]> {
    return this.http.get<PlanChange[]>(
      `${this.apiUrl}/billing/subscription/history`,
    );
  }

  /** Podgląd kwoty prorated przed potwierdzeniem (7.5 AC5). */
  getProration(plan: PlanName): Observable<Proration> {
    return this.http.get<Proration>(
      `${this.apiUrl}/billing/subscription/proration`,
      { params: { plan } },
    );
  }

  /** Lista faktur VAT tenanta (7.6 AC5) — malejąco po dacie, 20/stronę. */
  getInvoices(page = 1, size = 20): Observable<InvoiceList> {
    return this.http.get<InvoiceList>(`${this.apiUrl}/billing/invoices`, {
      params: { page, size },
    });
  }

  /** PDF faktury z MinIO (7.6 AC5) — blob do pobrania po stronie klienta. */
  getInvoicePdf(id: string): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/billing/invoices/${id}/pdf`, {
      responseType: "blob",
    });
  }

  /** Dane fakturowe tenanta (7.6 AC4) — inicjalizowane z profilu przy braku. */
  getInvoiceData(): Observable<InvoiceData> {
    return this.http.get<InvoiceData>(`${this.apiUrl}/billing/invoice-data`);
  }

  /** Aktualizacja danych fakturowych (7.6 AC4) — dotyczy następnych faktur. */
  updateInvoiceData(data: InvoiceData): Observable<InvoiceData> {
    return this.http.put<InvoiceData>(
      `${this.apiUrl}/billing/invoice-data`,
      data,
    );
  }
}
