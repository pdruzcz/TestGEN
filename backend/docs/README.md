# Dokumentacja backendu — przekierowanie

Dokumentacja implementacyjna platformy TestGEN została skonsolidowana w
katalogu **[`docs/final/`](../../docs/final/)** (Story 9.1; wcześniej model
Story 1.50 w `docs/p1/`).

Mapowanie historyczne (pliki z tego katalogu usunięte przy migracji 1.50,
ścieżki docelowe po konsolidacji 9.1):

| Źródło (usunięte) | Miejsce docelowe |
|-------------------|------------------|
| `ADR.md` | [`docs/final/architecture/adr/`](../../docs/final/architecture/adr/) (ADR-001..013) |
| `API.md` | [`docs/final/architecture/api/overview.md`](../../docs/final/architecture/api/overview.md) + [`examples/`](../../docs/final/architecture/api/examples/) |
| `GETTING_STARTED.md` | [`docs/final/deployment-guide/getting-started.md`](../../docs/final/deployment-guide/getting-started.md) + [`environment-setup.md`](../../docs/final/deployment-guide/environment-setup.md) |
| `EPIC_1_SUMMARY.md` | [`docs/final/architecture/system.md`](../../docs/final/architecture/system.md), [`workflows.md`](../../docs/final/architecture/workflows.md), [`ai-modules/`](../../docs/final/ai-modules/) |
| `EPIC_2_ANALYSIS.md` | [`docs/final/ai-modules/analiza-dokumentacji/`](../../docs/final/ai-modules/analiza-dokumentacji/) |

**Jedno miejsce prawdy:** po konsolidacji treść dokumentacji żyje wyłącznie w
`docs/final/`. Spis treści: [`docs/final/README.md`](../../docs/final/README.md).

Autorytatywna specyfikacja API maszyny pozostaje generowana z FastAPI:
`/openapi.json`, `/docs` (Swagger UI), `/redoc`.
