# Uruchamianie analizy luk

> Przewodnik — uruchamianie analizy luk funkcjonalnych.

## Wymagania wstępne

1. Projekt z co najmniej jednym dokumentem (SRS, SDD, user stories) — patrz
   moduł dokumentów.
2. Projekt z przeskanowanym kodem źródłowym — patrz moduł analizy.
3. Uprawnienia `write:projects` w tenant.

## Krok 1: Otwórz Project Detail

1. Zaloguj się do TestGEN.
2. Wybierz projekt z listy.
3. W sidebarze kliknij **Projekty → {twój projekt}** — otworzy się Project
   Detail z kafelkami akcji.

## Krok 2: Uruchom analizę luk

1. W sekcji akcji kliknij przycisk **"Luki funkcjonalne"**.
2. Otworzy się widok analizy luk (route: `/projects/:id/gap-analysis`).
3. Kliknij przycisk **"Uruchom analizę"** w prawym górnym rogu.
4. W oknie dialogowym wybierz:
   - **Dokumenty**: lista dokumentów SRS/SDD do analizy (auto-wykryte).
5. Kliknij **Potwierdź**.

## Krok 3: Monitoruj postęp

- Po uruchomieniu otrzymasz `task_id` (HTTP 202 Accepted).
- W nagłówku widoku pojawi się status: `pending` → `running` → `success` /
  `failed`.
- Średni czas analizy: < 5 s (małe projekty) / 30 s (duże).
- Po zakończeniu tabela findings odświeża się automatycznie.

## Krok 4: Interpretuj status

| Status | Znaczenie | Akcja |
|---|---|---|
| `pending` | Zadanie w kolejce | Czekaj |
| `running` | Analiza w toku | Czekaj |
| `success` | Ukończono pomyślnie | Tabela findings pokazuje wyniki |
| `failed` | Błąd | Sprawdź logi w `/projects/{id}/tasks` |

Analiza działa na deterministycznych algorytmach dopasowania — wyniki są
powtarzalne, a analiza nie wymaga dostępu do usług zewnętrznych. Nadaje się
do CI i szybkich iteracji.

## Krok 5: Automatyzacja (opcjonalne)

- **Celery beat**: skonfiguruj harmonogram w `app/workers/scheduler.py` aby
  uruchamiać analizę np. co noc.
- **API**: `POST /api/v1/projects/{project_id}/gap-analysis` z body
  `{"document_ids": [...]}`.

## Rozwiązywanie problemów

### "Brak wymagań"
Analiza wymaga `AnalysisResult(module="requirements")`. Najpierw uruchom analizę
dokumentu w module analizy.

### "Brak bytów kodu"
Analiza wymaga `AnalysisResult(module="logic_structures")`. Najpierw uruchom
skanowanie kodu.

## Następne kroki

- [02 — Interpretacja wyników](02-interpretacja-wynikow.md)
- [03 — Compliance i priorytetyzacja](03-compliance-i-priorytetyzacja.md)
