"""reset_demo.py — reset konta demo TestGEN (limit 10 analiz / plan freemium).

Dwie NIEZALEŻNE operacje, bo dwie rzeczy wliczają się w „zużycie" na demo:

  1. Limit 10 analiz (widget „Plan usage", HTTP 429 po przekroczeniu)
     żyje w **Redis** — klucz ``tenant:{id}:analysis_count:{YYYY-MM}``.
     → komenda ``reset-quota`` usuwa ten klucz (licznik → 0, kolejne analizy odblokowane).

  2. Karta „Analiz w tym miesiącu" + „Przypadki testowe" czytana jest z **bazy**
     (``analysis_results`` / ``test_cases``).
     → komenda ``purge`` usuwa rekordy analiz (kaskadowo: test_cases, test_case_executions)
       → dashboard czysty jak po świeżym koncie.

``reset`` = ``reset-quota`` + ``purge`` (pełny powrót do czysta, pliki źródłowe/projekty zostają).

SELEKCJA TENANTA
  --tenant <UUID>     operacja na jednym tenancie
  --plan freemium     wszyscy tenanci danego planu (domyślnie: freemium)
  --plan all          absolutnie wszyscy tenanci

URUCHOMIENIE (serwer demo — skrypt działa w kontenerze ``backend``, ma deps + sieć):
  docker compose exec backend python scripts/reset_demo.py status
  docker compose exec backend python scripts/reset_demo.py reset-quota --plan freemium --yes
  docker compose exec backend python scripts/reset_demo.py purge --tenant <UUID> --yes
  docker compose exec backend python scripts/reset_demo.py reset --plan freemium --yes

``status`` jest bezpieczne (tylko odczyt). ``reset-quota`` / ``purge`` / ``reset``
wymagają ``--yes`` (albo potwierdzenia interaktywnego, jeśli -T).
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import UTC, datetime

import asyncpg
import redis

from app.core.config import get_settings

settings = get_settings()

# UUID „zero" włącza politykę ``admin_bypass`` RLS — omija izolację tenantów.
# Tu jednak używamy prawdziwego tenant_id, by RLS samo ograniczyło zakres operacji
# (nawet przy pomyłce w klauzuli WHERE nie usuniemy danych innego tenanta).
ADMIN_BYPASS = "00000000-0000-0000-0000-000000000000"


# ── helpers ────────────────────────────────────────────────────────────────────


def _month_key() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


def _quota_key(tenant_id: str) -> str:
    return f"tenant:{tenant_id}:analysis_count:{_month_key()}"


def _pg_url() -> str:
    """``postgresql+asyncpg://...`` → URL zrozumiały dla sterownika asyncpg."""
    return settings.database_url.replace("postgresql+asyncpg://", "postgresql://")


def _redis() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


async def _connect_db() -> asyncpg.Connection:
    return await asyncpg.connect(_pg_url())


async def _list_tenants(conn: asyncpg.Connection, plan: str, tenant_id: str | None) -> list[tuple[str, str, str]]:
    """Zwraca listę (id, name, plan) pasujących do filtru."""
    if tenant_id:
        rows = await conn.fetch("SELECT id::text, name, plan::text FROM tenants WHERE id = $1", uuid.UUID(tenant_id))
    elif plan == "all":
        rows = await conn.fetch("SELECT id::text, name, plan::text FROM tenants ORDER BY created_at")
    else:
        rows = await conn.fetch(
            "SELECT id::text, name, plan::text FROM tenants WHERE plan = $1 ORDER BY created_at", plan
        )
    return [(r["id"], r["name"], r["plan"]) for r in rows]


async def _db_counts(conn: asyncpg.Connection, tenant_id: str) -> tuple[int, int]:
    """Liczy analizy i przypadki testowe tenanta (z kontekstem RLS)."""
    await conn.execute(f"SET app.current_tenant = '{tenant_id}'")
    analyses = await conn.fetchval("SELECT count(*) FROM analysis_results WHERE tenant_id = $1", uuid.UUID(tenant_id))
    test_cases = await conn.fetchval(
        """
        SELECT count(*) FROM test_cases tc
        JOIN analysis_results ar ON ar.id = tc.analysis_result_id
        WHERE ar.tenant_id = $1
        """,
        uuid.UUID(tenant_id),
    )
    return int(analyses), int(test_cases)


def _confirm(prompt: str) -> bool:
    try:
        return input(prompt).strip().lower() in {"y", "yes", "t", "tak"}
    except EOFError:
        print("  (brak interaktywnego TTY — podaj --yes, aby wykonać bez potwierdzenia)")
        return False


# ── komendy ────────────────────────────────────────────────────────────────────


async def cmd_status(plan: str, tenant_id: str | None) -> int:
    r = _redis()
    conn = await _connect_db()
    try:
        tenants = await _list_tenants(conn, plan, tenant_id)
        if not tenants:
            print("Brak tenantów pasujących do filtru.")
            return 0

        mk = _month_key()
        print(f"Zużycie analiz (miesiąc klucza Redis: {mk})")
        print("=" * 72)
        for tid, name, tpl in tenants:
            used = r.get(_quota_key(tid))
            used = int(used) if used else 0
            analyses, test_cases = await _db_counts(conn, tid)
            print(f"• {name}  [{tpl}]  id={tid}")
            print(f"    quota Redis (limit/zużyto): {used}  →  reset-quota aby wyzerować")
            print(f"    DB: analysis_results={analyses}, test_cases={test_cases}  →  purge aby wyczyścić")
        print("=" * 72)
        print("Podsumowanie: reset-quota odblokowuje kolejne analizy (Redis);")
        print("              purge czyści historię w DB (czysty dashboard).")
    finally:
        await conn.close()
    return 0


async def cmd_reset_quota(plan: str, tenant_id: str | None, yes: bool) -> int:
    r = _redis()
    targets = []
    conn = await _connect_db()
    try:
        tenants = await _list_tenants(conn, plan, tenant_id)
    finally:
        await conn.close()
    if not tenants:
        print("Brak tenantów pasujących do filtru.")
        return 0

    for tid, name, _ in tenants:
        used = int(r.get(_quota_key(tid)) or 0)
        targets.append((tid, name, used))

    print("Zostaną wyzerowane liczniki Redis (analizy w bieżącym miesiącu):")
    for tid, name, used in targets:
        print(f"  • {name}  ({used} → 0)   id={tid}")
    if not yes and not _confirm("Kontynuować? [y/N] "):
        print("Anulowano.")
        return 1

    for tid, name, _ in targets:
        deleted = r.delete(_quota_key(tid))
        print(f"  ✓ {name}: usunięto klucz Redis (deleted={deleted})")
    print("Gotowe — licznik quoty = 0. Można uruchomić kolejne analizy.")
    return 0


async def cmd_purge(plan: str, tenant_id: str | None, yes: bool) -> int:
    conn = await _connect_db()
    try:
        tenants = await _list_tenants(conn, plan, tenant_id)
        if not tenants:
            print("Brak tenantów pasujących do filtru.")
            return 0

        preview: list[tuple[str, str, int, int]] = []
        for tid, name, _ in tenants:
            analyses, test_cases = await _db_counts(conn, tid)
            preview.append((tid, name, analyses, test_cases))

        print("Zostaną usunięte analizy z DB (kaskadowo: test_cases, test_case_executions).")
        print("Projekty i pliki źródłowe pozostają nietknięte.")
        for tid, name, a, tc in preview:
            print(f"  • {name}: analysis_results={a}, test_cases={tc}   id={tid}")
        if not yes and not _confirm("Kontynuować? [y/N] "):
            print("Anulowano.")
            return 1

        for tid, name, _a, _tc in preview:
            # Kontekst RLS ustawiony na sesji → kaskada (test_cases/executions) też przechodzi.
            await conn.execute(f"SET app.current_tenant = '{tid}'")
            deleted = await conn.execute("DELETE FROM analysis_results WHERE tenant_id = $1", uuid.UUID(tid))
            n = deleted.split()[-1] if isinstance(deleted, str) else "?"
            print(f"  ✓ {name}: usunięto analiz = {n} (kaskadowo test_cases/executions)")
        await conn.execute("RESET app.current_tenant")
        print("Gotowe — historia analiz wyczyszczona.")
    finally:
        await conn.close()
    return 0


async def cmd_reset(plan: str, tenant_id: str | None, yes: bool) -> int:
    rc1 = await cmd_reset_quota(plan, tenant_id, yes)
    if rc1 != 0:
        return rc1
    # Po reset-quota --yes nie pytamy ponownie w purge (ta sama zgoda).
    return await cmd_purge(plan, tenant_id, yes=yes or True)


# ── CLI ────────────────────────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(
        description="Reset konta demo TestGEN (quota Redis + historia analiz DB).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_target(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--tenant", help="UUID pojedynczego tenanta")
        sp.add_argument(
            "--plan",
            default="freemium",
            choices=["freemium", "basic", "premium", "all"],
            help="Filtr planu (domyślnie: freemium)",
        )

    sp = sub.add_parser("status", help="Tylko odczyt — pokaż zużycie quoty i liczbę analiz.")
    add_target(sp)

    sp = sub.add_parser("reset-quota", help="Wyzeruj licznik Redis → odblokuj kolejne analizy.")
    add_target(sp)
    sp.add_argument("--yes", action="store_true", help="Bez potwierdzenia")

    sp = sub.add_parser("purge", help="Usuń analizy z DB (kaskadowo test_cases).")
    add_target(sp)
    sp.add_argument("--yes", action="store_true", help="Bez potwierdzenia")

    sp = sub.add_parser("reset", help="reset-quota + purge (pełny powrót do czysta).")
    add_target(sp)
    sp.add_argument("--yes", action="store_true", help="Bez potwierdzenia")

    args = p.parse_args()

    try:
        if args.cmd == "status":
            return asyncio_run(cmd_status(args.plan, args.tenant))
        if args.cmd == "reset-quota":
            return asyncio_run(cmd_reset_quota(args.plan, args.tenant, args.yes))
        if args.cmd == "purge":
            return asyncio_run(cmd_purge(args.plan, args.tenant, args.yes))
        if args.cmd == "reset":
            return asyncio_run(cmd_reset(args.plan, args.tenant, args.yes))
    except (asyncpg.PostgresError, redis.RedisError) as exc:
        print(f"BŁĄD: {exc}", file=sys.stderr)
        print("  Sprawdź czy kontenery postgres/redis działają i czy .env ma poprawne URL-e.", file=sys.stderr)
        return 2
    return 0


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


if __name__ == "__main__":
    sys.exit(main())
