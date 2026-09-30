# Konwencje kodu — TestGEN (P1)

## Nazewnictwo

| Element | Konwencja | Przykład |
|---------|-----------|----------|
| Plik Python | `snake_case.py` | `requirement_extractor.py` |
| Klasa Python | `PascalCase` | `RequirementExtractor` |
| Komponent Angular | `kebab-case.component.ts` | `document-view.component.ts` |
| Endpoint REST | `kebab-case`, rzeczownik w l. mnogiej | `/api/v1/test-cases` |
| Tabela SQL | `snake_case`, l. mnoga | `source_files`, `analysis_results` |
| Zmienna środowiskowa | `UPPER_SNAKE` | `DATABASE_URL` |
| Branch gita | `feature/*`, `fix/*`, `hotfix/*`, `docs/*` | `feature/2-13-docs-api` |

## Struktura katalogów

```
backend/
  app/
    api/routes/        # routery FastAPI (per domena)
    services/          # logika domenowa (analysis/, auth/, ...)
    models/            # modele SQLAlchemy (RLS, TenantMixin)
    schemas/           # schematy Pydantic
    workers/           # zadania Celery (tasks/, celery_app.py)
    core/              # config, database, security, cookies, storage
  alembic/versions/    # migracje
  tests/               # unit / integration / golden_data
frontend/
  src/app/             # standalone components, Material, signals
docs/final/            # ta dokumentacja (user-guide, deployment-guide,
                       # admin-guide, architecture, ai-modules,
                       # troubleshooting, release-notes)
```

## Testy

| Typ | Lokalizacja | Narzędzie |
|-----|-------------|-----------|
| Jednostkowe (backend) | `backend/tests/unit/` | pytest |
| Integracyjne (backend) | `backend/tests/integration/` | pytest |
| Golden data | `backend/tests/golden_data/` | pytest, marker `@golden` |
| Frontend | `frontend/` | Vitest/Karma |

- Pokrycie backendu ≥ 80% (bramka CI: `--cov-fail-under=80`).
- Każda nowa funkcjonalność wymaga testów jednostkowych + integracyjnych.
- Zmiana zachowania analizy = aktualizacja ground truth, nie obniżenie progu
  ([ADR-008](./adr/ADR-008-golden-data.md)).

## Git flow

- `main` — stabilna, produkcja.
- `develop` — integracja.
- `feature/*`, `fix/*`, `hotfix/*`, `docs/*` — praca tematyczna.
- PR wymaga **min. 1 approve** i zielonego CI.

## Commity

**Conventional Commits z emoji** (zgodnie z historią repo i `commitlint`):

```
✨ feat(scope): krótki opis po polsku (Story X.Y, ACn)
🐛 fix(scope): opis poprawki
📝 docs(p1): opis zmiany dokumentacji
♻️ refactor(scope): opis
✅ test(scope): opis
```

- Język komunikatów: polski dla opisu, angielski dla typu (`feat`/`fix`/...).
- Referencja do story i AC w treści (np. `Story 2.13, AC1`).
- **Bez `--no-verify`** — pre-commit `ruff`/`ruff-format` auto-naprawia pliki;
  przy niepowodzeniu: `git add -A` i ponowić commit.

## Linting / formatowanie

- Backend: `ruff check`, `ruff format` (`make lint`, `make format`).
- Frontend: `ng lint`, Prettier.
- Reguła TC001 egzekwowana — importy type-only pod `if TYPE_CHECKING:`.

## Code review

- Min. 1 approve, CI green.
- Nowy endpoint → polski `summary`/`description` + przykłady w OpenAPI
  ([api/overview.md](./api/overview.md)).
- Nowa tabela → `tenant_id` + polityka RLS + migracja Alembic.
