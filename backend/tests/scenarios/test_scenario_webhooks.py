"""Scenariusze 11-12 (AC11/AC12) — webhooki: idempotentność, chargeback,
rozbieżność kwot; dunning 3 prób → downgrade do Freemium + grace (CR#2).

E2E z mockami tpay (Task 5.1). Harmonogram dunningu D+1/D+3/D+5 testowany
mockiem czasu — ``SubscriptionScheduler.run(now=...)`` przyjmuje chwilę
przebiegu (seam testowy 7.2), progi cooldownu liczone od realnego „teraz",
stąd przesunięcia przebiegów o 2 dni (zawsze > poprzedni offset 1/3/5 dni).
Po 3. PONOWIENIU (4. porażce): ``past_due`` + downgrade ZAWSZE do Freemium
z 7-dniowym grace na planie, który był; po wygaśnięciu grace — limity
Freemium egzekwowane (429 ``limit_reached``).
"""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import QuotaExceededError, TestGENError
from app.models.payment import PaymentStatus, WebhookEvent
from app.models.subscription import SubscriptionStatus
from app.models.subscription_plan import PlanName
from app.models.usage import CounterType
from app.services.billing.providers.tpay.client import TpayApiError
from app.services.billing.quota_service import QuotaService
from app.services.billing.subscription_scheduler import SubscriptionScheduler
from app.services.billing.webhook_processor import WebhookProcessor
from tests.fixtures.billing_fixtures import (
    added_objects,
    billing_emails_mocked,
    in_days,
    invoice_pipeline_mocked,
    make_mock_db,
    make_payment_txn,
    make_plans,
    make_scenario_provider,
    make_subscription,
    now_utc,
    paid_webhook_db,
    saved_card_token,
    scalar,
    scalars,
)
from tests.fixtures.tpay_fixtures import build_notification, sign_jws
from tests.fixtures.usage_fixtures import make_counter


class TestScenario11WebhookIdempotencyAndChargeback:
    """AC11 — duplikat event_uid, chargeback, rozbieżność tr_paid/tr_amount."""

    async def test_duplicate_event_uid_skips_processing_answers_true(self):
        """tpay ponawia tę samą notyfikację → pominięcie, TRUE, bez podwójnej
        aktywacji (audyt: DUPLICATE)."""
        plans = make_plans()
        basic = plans[PlanName.BASIC]
        provider = make_scenario_provider()
        tenant_id = uuid.uuid4()
        sub = make_subscription(plans[PlanName.FREEMIUM], tenant_id)
        txn = make_payment_txn(tenant_id, meta={"plan": "basic"})

        # Pierwsze przetworzenie: aktywacja + wpis audytu processed.
        db_first = paid_webhook_db(txn, basic, sub)
        notification = build_notification(tr_crc=txn.hidden_description)
        with billing_emails_mocked(), invoice_pipeline_mocked():
            ok, status = await WebhookProcessor(db_first, provider).handle_tpay_notification(
                notification, sign_jws(notification)
            )
        assert (ok, status) == (True, "processed")
        assert sub.plan_id == basic.id
        (event,) = [e for e in added_objects(db_first) if isinstance(e, WebhookEvent)]
        assert event.processing_status == "processed"

        # Duplikat (ten sam event_uid — identyczny payload): pominięcie.
        db_duplicate = make_mock_db(
            MagicMock(),  # SET LOCAL RLS
            scalar(event),  # dedup: zdarzenie już processed
        )
        with billing_emails_mocked() as emails, invoice_pipeline_mocked() as (_inv, pdf_task):
            ok2, status2 = await WebhookProcessor(db_duplicate, provider).handle_tpay_notification(
                notification, sign_jws(notification)
            )
        assert (ok2, status2) == (True, "duplicate")  # TRUE przerywa serię ponowień tpay
        assert not db_duplicate.add.call_args_list  # brak nowych efektów/audytów
        pdf_task.delay.assert_not_called()
        emails["confirmation"].assert_not_called()
        assert sub.plan_id == basic.id  # bez podwójnej aktywacji

    async def test_paid_webhook_uppercase_true_activates(self):
        """Sandbox tpay wysyła ``tr_status='TRUE'`` (wielkie litery), choć
        dokumentacja klasycznego API pokazuje 'true' — porównanie musi być
        bezrolkowe, inaczej opłacona transakcja spada do ``charged_back``
        (wykryte na sandboxie 2026-09-14: notyfikacja processed, plan
        nieaktywowany, status charged_back)."""
        plans = make_plans()
        basic = plans[PlanName.BASIC]
        provider = make_scenario_provider()
        tenant_id = uuid.uuid4()
        sub = make_subscription(plans[PlanName.FREEMIUM], tenant_id)
        txn = make_payment_txn(tenant_id, meta={"plan": "basic"})

        db = paid_webhook_db(txn, basic, sub)
        notification = build_notification(tr_crc=txn.hidden_description, tr_status="TRUE")
        with billing_emails_mocked(), invoice_pipeline_mocked():
            ok, status = await WebhookProcessor(db, provider).handle_tpay_notification(
                notification, sign_jws(notification)
            )
        assert (ok, status) == (True, "processed")
        assert txn.status == PaymentStatus.PAID
        assert sub.plan_id == basic.id  # aktywacja planu

    async def test_chargeback_flags_manual_review_without_downgrade(self):
        """``tr_status=chargeback`` → ``charged_back`` + flaga ręcznej weryfikacji,
        bez automatycznego downgrade'u subskrypcji."""
        plans = make_plans()
        provider = make_scenario_provider()
        tenant_id = uuid.uuid4()
        sub = make_subscription(plans[PlanName.BASIC], tenant_id, days=20)  # aktywna
        txn = make_payment_txn(tenant_id, meta={"plan": "basic", "source": "recurring"})

        db = make_mock_db(MagicMock(), scalar(None), scalar(txn))
        notification = build_notification(tr_crc=txn.hidden_description, tr_status="chargeback", tr_paid="30.00")
        ok, status = await WebhookProcessor(db, provider).handle_tpay_notification(notification, sign_jws(notification))
        assert (ok, status) == (True, "processed")
        assert txn.status == PaymentStatus.CHARGED_BACK
        assert txn.meta.get("manual_review") is True  # flaga do ręcznej weryfikacji
        assert sub.status == SubscriptionStatus.ACTIVE  # bez automatycznego downgrade'u
        assert sub.plan_id == plans[PlanName.BASIC].id

    async def test_amount_mismatch_flagged_not_activated(self):
        """``tr_paid != tr_amount`` → flaga rozbieżności (paid_amount zapisany,
        alert w logach), bez aktywacji."""
        plans = make_plans()
        provider = make_scenario_provider()
        tenant_id = uuid.uuid4()
        sub = make_subscription(plans[PlanName.FREEMIUM], tenant_id)
        txn = make_payment_txn(tenant_id, meta={"plan": "basic"})

        db = make_mock_db(MagicMock(), scalar(None), scalar(txn))
        notification = build_notification(
            tr_crc=txn.hidden_description, tr_amount="30.00", tr_paid="10.00", tr_status="true"
        )
        ok, _status = await WebhookProcessor(db, provider).handle_tpay_notification(
            notification, sign_jws(notification)
        )
        assert ok is True
        assert txn.status == PaymentStatus.CHARGED_BACK  # rozbieżność → ręczna weryfikacja
        assert txn.paid_amount == Decimal("10.00")  # wpłacone odnotowane (alert)
        assert sub.plan_id == plans[PlanName.FREEMIUM].id  # bez aktywacji


class TestScenario12DunningFullCycle:
    """AC12 — 3 próby dunningu → downgrade do Freemium + grace + 429 po grace."""

    @pytest.mark.parametrize("plan_key", ["basic", "premium"], ids=["basic", "premium"])
    async def test_dunning_downgrades_to_freemium_with_grace(self, plan_key):
        plans = make_plans()
        plan = plans[PlanName(plan_key)]
        freemium = plans[PlanName.FREEMIUM]
        tenant_id = uuid.uuid4()
        provider = make_scenario_provider()
        provider.charge_recurring = AsyncMock(side_effect=TpayApiError(402, "err: payment declined"))
        token = saved_card_token(tenant_id)
        sub = make_subscription(plan, tenant_id, days=-1)  # next_charge_at minionęło
        sub.payment_token_id = token.id

        async def failing_run(at, *, with_downgrade: bool = False) -> dict:
            results = [
                scalars(sub),  # skan odnowień
                scalars(),  # skan wygasłych grace
                scalars(),  # skan downgrade'ów
                scalar(plan),  # plan odnowienia
                scalar(token),  # metoda płatności
                scalar("owner@testcompany.pl"),  # email Ownera
            ]
            if with_downgrade:
                results.append(scalar(freemium))  # _apply_dunning_downgrade: plan Freemium
            db = make_mock_db(*results)
            return await SubscriptionScheduler(db, provider).run(now=at)

        # Odrzucone obciążenie inicjujące + 3 ponowienia D+1/D+3/D+5 (mock czasu:
        # przebiegi co 2 dni — zawsze po poprzednim offsecie cooldownu).
        with billing_emails_mocked() as emails:
            await failing_run(now_utc())  # porażka 1 → retry D+1
            assert sub.dunning_attempt == 1
            await failing_run(in_days(2))  # porażka 2 → retry D+3
            assert sub.dunning_attempt == 2
            await failing_run(in_days(4))  # porażka 3 → retry D+5
            assert sub.dunning_attempt == 3
            await failing_run(in_days(6), with_downgrade=True)  # porażka 4 → downgrade

            # Powiadomienia email (mock): przy każdej próbie ponowienia (1-3)
            # oraz o downgrade — czwarta porażka kończy się mailem o downgrade
            # (zastępuje „próba nieudana"), patrz register_failed_charge.
            assert emails["payment_failed"].call_count == 3
            emails["downgraded"].assert_called_once()

        # Po 3 próbach: past_due → downgrade ZAWSZE do Freemium + grace 7 dni.
        assert sub.status == SubscriptionStatus.PAST_DUE
        assert sub.plan_id == freemium.id
        assert sub.previous_plan_id == plan.id  # plan przed downgrade'em
        assert sub.grace_until is not None and sub.grace_until > now_utc()
        assert (sub.grace_until - now_utc()).days <= 7
        assert sub.dunning_next_retry_at is None

        # W grace obowiązują limity planu dotychczasowego (np. basic: 50 analiz).
        counter = make_counter(tenant_id, value=49, limit_value=50)
        db_grace = make_mock_db(scalar(sub), scalar(plan), scalar(counter))
        assert await QuotaService(db_grace).check_quota(tenant_id, CounterType.ANALYSES) is True

        # Po wygaśnięciu grace scheduler egzekwuje Freemium (tenants.plan).
        # Upływ 7 dni symulujemy na danych (grace_until w przeszłości) —
        # enforce_grace_expiry rewaliduje progi zegarem wall-clock, więc
        # sam „przyszły" run(now=...) nie wystarczy (szew testowy, nie bug).
        sub.grace_until = now_utc() - timedelta(days=1)
        db_expire = make_mock_db(
            scalars(),  # skan odnowień (past_due → poza)
            scalars(sub),  # skan wygasłych grace
            scalars(),  # skan downgrade'ów
            MagicMock(),  # UPDATE tenants.plan → freemium
        )
        stats = await SubscriptionScheduler(db_expire, provider).run(now=now_utc())
        assert stats.get("grace_expired") == 1
        assert sub.grace_until is None

        # Limity Freemium egzekwowane: 429 przy przekroczeniu limitu analiz.
        exhausted = make_counter(tenant_id, value=10, limit_value=10)
        db_limit = make_mock_db(scalar(sub), scalar(freemium), scalar(exhausted))
        with pytest.raises(QuotaExceededError) as excinfo:
            await QuotaService(db_limit).enforce_quota(tenant_id, CounterType.ANALYSES)
        err = excinfo.value
        assert isinstance(err, TestGENError)
        assert err.status_code == 429  # mapping RFC7807 → API 429
        assert err.extra["error"] == "limit_reached"
        assert err.extra["resource"] == "analyses"
        assert err.extra["limit"] == 10
        assert err.extra["current"] == 10
        assert err.extra["plan"] == "freemium"
        assert err.extra["upgrade_url"] == "/billing/plans"  # FE: upgrade CTA
