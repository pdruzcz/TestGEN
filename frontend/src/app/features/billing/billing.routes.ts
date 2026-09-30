import { Routes } from "@angular/router";

import { BillingLayoutComponent } from "./billing-layout/billing-layout.component";

/**
 * Lazy routing modułu billing (Story 7.1 + 7.4 + 7.2 + 7.6).
 *
 * Wszystkie strony są dziećmi `BillingLayoutComponent` (nagłówek + stopka
 * — wspólna powłoka E7, wzór: powłoka panelu admina 6.15).
 *
 * `plans` — porównanie planów (7.1); `checkout*` — przepływ tpay (7.4):
 * init (przekierowanie na Panel Transakcyjny), strony powrotu
 * success/error z pollingiem statusu; `payment-methods*` — zapisane karty
 * i aliasy BLIK (7.2): lista + rejestracja karty bez obciążenia + powrót
 * z rejestracji (polling potwierdzenia); `invoices` — lista faktur VAT
 * z pobieraniem PDF (7.6 AC5); `invoice-data` — dane fakturowe tenanta
 * (7.6 AC4); `usage` — dashboard zużycia zasobów (7.9); `subscription` —
 * szczegóły subskrypcji z anulowaniem/reaktywacją (7.7); `transactions` —
 * historia transakcji z filtrami i paginacją (7.7).
 */
export const BILLING_ROUTES: Routes = [
  {
    path: "",
    component: BillingLayoutComponent,
    children: [
      { path: "", redirectTo: "plans", pathMatch: "full" },
      {
        path: "plans",
        title: "Plany subskrypcji — TestGEN",
        loadComponent: () =>
          import("./plan-comparison/plan-comparison.component").then(
            (m) => m.PlanComparisonComponent,
          ),
      },
      // Story 7.4 — inicjacja checkoutu tpay (strona docelowa CTA "Wybierz Basic/Premium")
      {
        path: "checkout",
        title: "Płatność — TestGEN",
        loadComponent: () =>
          import("./subscription-manage/checkout-init/checkout-init.component").then(
            (m) => m.CheckoutInitComponent,
          ),
      },
      // Story 7.4 — strony powrotu (polling statusu transakcji)
      {
        path: "checkout/success",
        title: "Potwierdzenie płatności — TestGEN",
        loadComponent: () =>
          import("./subscription-manage/checkout-success/checkout-success.component").then(
            (m) => m.CheckoutSuccessComponent,
          ),
      },
      {
        path: "checkout/error",
        title: "Płatność nieudana — TestGEN",
        loadComponent: () =>
          import("./subscription-manage/checkout-error/checkout-error.component").then(
            (m) => m.CheckoutErrorComponent,
          ),
      },
      // Story 7.2 — metody płatności (karty / aliasy BLIK; pełny portal w 7.7)
      {
        path: "payment-methods",
        title: "Metody płatności — TestGEN",
        loadComponent: () =>
          import("./payment-methods/payment-methods.component").then(
            (m) => m.PaymentMethodsComponent,
          ),
      },
      // Story 7.2 — powrót z rejestracji karty (callbackUrl POST /tokens u tpay)
      {
        path: "payment-methods/return",
        title: "Powrót z rejestracji karty — TestGEN",
        loadComponent: () =>
          import("./payment-methods/payment-methods-return.component").then(
            (m) => m.PaymentMethodsReturnComponent,
          ),
      },
      // Story 7.6 — lista faktur VAT (Owner/User) z pobieraniem PDF (AC5)
      {
        path: "invoices",
        title: "Faktury — TestGEN",
        loadComponent: () =>
          import("./invoice-list/invoice-list.component").then(
            (m) => m.InvoiceListComponent,
          ),
      },
      // Story 7.6 — dane fakturowe tenanta (Owner, AC4)
      {
        path: "invoice-data",
        title: "Dane fakturowe — TestGEN",
        loadComponent: () =>
          import("./invoice-data/invoice-data.component").then(
            (m) => m.InvoiceDataComponent,
          ),
      },
      // Story 7.7 — szczegóły subskrypcji (AC3): plan, okres, metoda płatności,
      // anulowanie z potwierdzeniem (AC4) i reaktywacja (AC5)
      {
        path: "subscription",
        title: "Subskrypcja — TestGEN",
        loadComponent: () =>
          import("./subscription-manage/subscription-detail/subscription-detail.component").then(
            (m) => m.SubscriptionDetailComponent,
          ),
      },
      // Story 7.7 — historia transakcji (AC2): filtry statusu/zakresu dat, paginacja
      {
        path: "transactions",
        title: "Historia transakcji — TestGEN",
        loadComponent: () =>
          import("./transaction-list/transaction-list.component").then(
            (m) => m.TransactionListComponent,
          ),
      },
      // Story 7.9 — dashboard zużycia zasobów (karty z paskami postępu, okres,
      // prognoza limitu analiz, historia na wykresie po rozwinięciu karty)
      {
        path: "usage",
        title: "Zużycie zasobów — TestGEN",
        loadComponent: () =>
          import("./usage-dashboard/usage-dashboard.component").then(
            (m) => m.UsageDashboardComponent,
          ),
      },
    ],
  },
];
