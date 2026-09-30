# Workflow dla deweloperów — TestGEN (P1)

Przepisy na najczęstsze zadania rozwojowe. Konwencje: [conventions.md](./conventions.md).

## Dodanie nowego języka parsera (AST)

Analiza kodu oparta na tree-sitter ([ADR-005](./adr/ADR-005-tree-sitter-parser.md)).

1. Dodaj grammar tree-sitter dla języka w module parserów (`backend/app/` obsługa
   języków).
2. Zarejestruj język w rejestrze parserów (mapowanie rozszerzenie → grammar).
3. Dodaj próbki golden data (kod + oczekiwane `logic_structures`).
4. Testy: ekstrakcja funkcji/klas/importów/parametrów.
5. Dokumentacja: zaktualizuj [ai/ast-analysis.md](../ai-modules/analiza-kodu/ast-analysis.md).

## Dodanie nowego frameworku testowego

Generowanie kodu przez Jinja2 ([ADR-006](./adr/ADR-006-jinja2-template-engine.md)).

1. Utwórz szablon Jinja2 w katalogu szablonów testowych (jednostkowy lub E2E —
   patrz [ADR-007](./adr/ADR-007-e2e-frameworks.md)).
2. Zarejestruj framework w rejestrze frameworków.
3. Dodaj próbki golden data: scenariusz → oczekiwany kod.
4. Testy regresyjne stabilności szablonu.
5. Dokumentacja: zaktualizuj [ai/test-code-generation.md](../ai-modules/analiza-kodu/test-code-generation.md).

## Dodanie nowego formatu dokumentacji

Pipeline natywny ([ai/document-analysis.md](../ai-modules/analiza-dokumentacji/document-analysis.md)).

1. Utwórz parser w `backend/app/services/analysis/document/` zwracający
   `ParsedDocument`.
2. Zarejestruj rozszerzenie w `get_document_parser()`.
3. Dodaj detekcję nagłówków w preprocesorze (`DocumentPreprocessor`).
4. Próbki golden data (dokument + ground truth sekcji/wymagań).
5. Testy + zaktualizuj [ai/document-formats.md](../ai-modules/analiza-dokumentacji/document-formats.md).

## Dodanie nowej reguły analizy dokumentacji

1. Zaimplementuj regułę w odpowiednim serwisie
   (`requirement_extractor`, `inconsistency_detector`, `glossary_extractor`…).
2. Dodaj próbkę golden data weryfikującą regułę.
3. Zaktualizuj progi w `docs_thresholds.json` jeśli reguła zmienia liczności.
4. Test + dokumentacja w [ai/document-analysis.md](../ai-modules/analiza-dokumentacji/document-analysis.md).

## Dodanie nowej tabeli (z RLS)

1. Model SQLAlchemy z `TenantMixin` (`tenant_id`) w `backend/app/models/`.
2. Migracja Alembic + **polityka RLS** na tabeli.
3. Schemat Pydantic + router (polski `summary`/`description`, przykłady).
4. Testy z ustawionym kontekstem `app.current_tenant`.

## Uruchomienie zadania asynchronicznego lokalnie

```bash
make celery-worker          # worker kolejki default
make celery-beat            # scheduler (zadania cykliczne)
make celery-flower          # UI monitoringu (http://localhost:5555)
make celery-inspect         # aktywne zadania
```

Kolejki tematyczne: `default`, `analysis`, `export`, `security`
([ADR-004](./adr/ADR-004-celery-rabbitmq.md)).

## Aktualizacja golden data przy celowej zmianie

1. Zmień kod analizy.
2. Wygeneruj na nowo ground truth:
   `_generate_samples.py`, `_generate_ground_truth.py`.
3. Zweryfikuj metryki vs progi (`pytest tests/golden_data/ -m golden -v`).
4. Zaktualizuj [ai/benchmarks.md](../ai-modules/analiza-kodu/benchmarks.md) po release.
