# Faktury VAT

> Dokumentacja P2, Epic 7 — Story 7.6 (FR57).
> Implementacja: `backend/app/services/billing/invoice_service.py`,
> modele `backend/app/models/invoice.py` / `invoice_data.py`.

## 1. Cykl życia faktury

Hook w `WebhookProcessor.mark_paid` (po opłacanej transakcji) →
`InvoiceService.generate_invoice`:

1. **Idempotencja po `payment_id`** — faktura dla transakcji już istnieje
   → zwraca istniejącą (webhooki tpay mogą przyjść wielokrotnie).
2. Snapshoty stron: sprzedawca z env (`INVOICE_SELLER_*`), nabywca z
   `invoice_data` tenanta (dane fakturowe, Story 7.6 AC4). Snapshot w
   rekordzie faktury — zmiana env/danych **nie dotyka** już wystawionych
   faktur.
3. Podział VAT: stawka **23%**, brutto → (netto, VAT) z ROUND_HALF_UP
   na groszach (`split_vat`).
4. Numeracja (sekcja 2), pozycja faktury z opisem okresu.
5. `render_and_deliver`: PDF (reportlab) → MinIO → email z załącznikiem.

Format kwot: polski separator (`format_pln` — `30,00`), kwoty w rekordzie
jako `str` (JSONB nie przechowuje Decimal; precyzja zachowana).

## 2. Numeracja — `FV/{rok}/{miesiąc}/{sekwencja}`

Przykład: `FV/2026/06/0001`. Sekwencja **per miesiąc kalendarzowy**,
pole `sequential_number` + unikat `(year, month, sequential_number)`.

Współbieżność (wyścig na pierwszy numer miesiąca — AC6):

- legalny lock numeracji w webhooku (nie transakcyjny SELECT … FOR UPDATE
  na całości — webhook musi się szybko committing),
- **savepoint + retry** — porażka `unique_violation` cofa tylko tę fakturę
  (savepoint), nie transakcję webhooka; do 3 prób
  (`_NUMBERING_ATTEMPTS`).

## 3. PDF, storage, wysyłka

| Krok | Szczegóły |
|---|---|
| Render PDF | reportlab, szablon Jinja2 (`_render_pdf`, `_template_context`) |
| Storage | MinIO, bucket **`testgen-invoices`**, klucz `{tenant_id}/{rok}/{miesiąc:02d}/{numer}.pdf` (`invoice_pdf_object_name`) |
| Wysyłka | Email do Ownera tenanta z załącznikiem PDF (Graph `fileAttachment`) |
| Błędy wysyłki | Nie wywracają webhooka — faktura istnieje, PDF do pobrania z portalu |

## 4. Dane fakturowe tenanta (AC4)

`invoice_data` (migracja 048): nazwa, NIP, adres — osobno od profilu
tenanta:

- `GET /api/v1/billing/invoice-data` (Owner) — brak rekordu → inicjalizacja
  z profilu tenanta (nazwa, NIP),
- `PUT /api/v1/billing/invoice-data` (Owner) — zmiana dotyczy wyłącznie
  **następnych** faktur; wystawione trzymają snapshot z chwili wystawienia.

## 5. API faktur

| Endpoint | Rola | Opis |
|---|---|---|
| `GET /api/v1/billing/invoices` | Owner, User | Lista faktur (paginacja 20) |
| `GET /api/v1/billing/invoices/{id}/pdf` | Owner, User | Pobranie PDF (stream z MinIO) |
| `GET /api/v1/billing/invoice-data` | Owner | Dane fakturowe |
| `PUT /api/v1/billing/invoice-data` | Owner | Aktualizacja danych fakturowych |

Frontend: `/billing/invoices` (lista + pobieranie PDF, AC5) i
`/billing/invoice-data` (formularz Ownera).
