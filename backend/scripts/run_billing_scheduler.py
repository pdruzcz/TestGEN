#!/usr/bin/env python
"""Jednorazowy przebieg SubscriptionScheduler — scenariusze odnowień na sandboxu (7.12).

Na środowisku testowym beat Celery odnowi subskrypcję dopiero o wyznaczonej
porze (codzienny przebieg + ``next_charge_at`` tenanta). Ten skrypt wywołuje
``SubscriptionScheduler.run()`` RAZ, natychmiast (wzorzec workera
``billing_tasks``: prywatna sesja ``task_session`` + kontekst RLS admina
NIL UUID) — do scenariuszy 9-10 runbooka sandboxa (odnowienie tokenem karty /
aliasem BLIK PAYID, dunning).

Uruchomienie (z katalogu ``backend/``, z env sandboxa):

    python scripts/run_billing_scheduler.py

Wymaga: ``DATABASE_URL`` + sekrety tpay (``TPAY_*``) + ``TPAY_ENV=sandbox``
w środowisku (na serwerze testowym: ``docker compose exec backend python
scripts/run_billing_scheduler.py``).
"""

import asyncio
import json
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


async def _run() -> dict:
    from sqlalchemy import text

    from app.core.config_billing import get_billing_settings
    from app.core.constants import NIL_UUID
    from app.core.database import task_session
    from app.services.billing.providers.tpay import TpayProvider
    from app.services.billing.subscription_scheduler import SubscriptionScheduler

    settings = get_billing_settings()
    if not settings.is_sandbox:
        print("ODMOWA: TPAY_ENV != sandbox — skrypt wyłącznie dla środowiska testowego", file=sys.stderr)
        raise SystemExit(2)

    provider = TpayProvider(settings)
    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{NIL_UUID}'"))
        stats = await SubscriptionScheduler(session, provider).run()
        await session.commit()
    return stats


if __name__ == "__main__":
    stats = asyncio.run(_run())
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if not stats:
        print("Brak subskrypcji do przetworzenia (sprawdź next_charge_at/dunning_next_retry_at tenanta).")
