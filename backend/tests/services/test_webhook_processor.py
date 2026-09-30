"""Testy dispatchera notyfikacji tpay — Story 7.3 (AC2, AC3, AC4, AC5).

Macierz typów (Task 6.1): transakcja (7.4, nietknięta), JSON tokenizacja
(``data.token``), aliasy BLIK (``ALIAS_*``), nieobsługiwane typy → skipped.
Wzorzec mockowanej sesji DB jak w ``test_tpay_webhooks.py`` — sekwencje
``db.execute`` opisane per test.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.payment import (
    PaymentStatus,
    PaymentToken,
    PaymentTransaction,
    TokenKind,
    TpayTokenStatus,
    WebhookEvent,
    WebhookProcessingStatus,
)
from app.models.subscription import Subscription, SubscriptionStatus
from app.services.billing.providers.tpay import TpayProvider
from app.services.billing.webhook_processor import WebhookProcessor
from tests.fixtures.billing_fixtures import savepoint_cm
from tests.fixtures.tpay_fixtures import (
    build_alias_notification,
    build_notification,
    build_tokenization_notification,
    make_test_billing_settings,
    sign_jws,
    signing_cert_pem,
)


def _provider() -> TpayProvider:
    return TpayProvider(make_test_billing_settings(), pinned_cert_pem=signing_cert_pem())


def _exec_scalar(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


def _alias_registration_txn(alias_value: str) -> PaymentTransaction:
    """Transakcja checkoutu z wygenerowaną wartością aliasu w meta (Task 1)."""
    return PaymentTransaction(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        provider="tpay",
        transaction_id="ta_ALIAS1",
        hidden_description="ord-alias-1",
        amount=Decimal("30.00"),
        currency="PLN",
        status=PaymentStatus.PAID,
        meta={"plan": "basic", "payer_email": "owner@test.com", "blik_alias_value": alias_value},
    )


def _blik_alias_token(tenant_id: uuid.UUID, alias_value: str) -> PaymentToken:
    from app.services.billing.subscription_service import encrypt_token_value, token_digest

    return PaymentToken(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        kind=TokenKind.BLIK_ALIAS_PAYID,
        value_encrypted=encrypt_token_value(tenant_id, alias_value),
        value_digest=token_digest(tenant_id, alias_value),
        tpay_status=TpayTokenStatus.ACTIVE,
        is_default=True,
    )


def _active_subscription(tenant_id: uuid.UUID) -> Subscription:
    return Subscription(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        plan_id=uuid.uuid4(),
        status=SubscriptionStatus.ACTIVE,
        next_charge_at=datetime(2026, 10, 1, tzinfo=UTC),
        cancel_at_period_end=False,
    )


class TestDispatchClassification:
    """AC2 — macierz typów: dispatch po content-type/strukturze."""

    async def test_alias_notification_routed_to_alias_handler(self):
        """ALIAS_REGISTER z dopasowaną transakcją rejestracji → PaymentToken ACTIVE."""
        txn = _alias_registration_txn("tg-abc")
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL RLS
                _exec_scalar(None),  # dedup: brak zdarzenia
                _exec_scalar(txn),  # transakcja rejestracji po meta.blik_alias_value
                _exec_scalar(None),  # dedup tokenu (value_digest) — nowy alias
                _exec_scalar(None),  # subskrypcja: brak → bez _link_default_method... (jest flush)
            ]
        )
        body = build_alias_notification(event="ALIAS_REGISTER", alias_value="tg-abc")

        ok, status = await WebhookProcessor(db, _provider()).handle_tpay_notification(body, sign_jws(body))

        assert (ok, status) == (True, WebhookProcessingStatus.PROCESSED.value)
        added = [c.args[0] for c in db.add.call_args_list]
        token = next(o for o in added if isinstance(o, PaymentToken))
        assert token.tenant_id == txn.tenant_id
        assert token.kind == TokenKind.BLIK_ALIAS_PAYID
        assert token.tpay_status == TpayTokenStatus.ACTIVE
        assert token.expires_at is not None
        # audyt: WebhookEvent typu alias z surowym payloadem
        event = next(o for o in added if isinstance(o, WebhookEvent))
        assert event.type == "alias"
        assert event.event_uid == "alias:ALIAS_REGISTER:tg-abc"
        assert event.raw["msg_value[value]"] == "tg-abc"

    async def test_alias_register_uid_kind_from_notification(self):
        """msg_value[type]=UID → kind blik_alias_uid."""
        txn = _alias_registration_txn("tg-uid-1")
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),
                _exec_scalar(None),
                _exec_scalar(txn),
                _exec_scalar(None),
                _exec_scalar(None),
            ]
        )
        body = build_alias_notification(event="ALIAS_REGISTER", alias_value="tg-uid-1", alias_type="UID")

        ok, _ = await WebhookProcessor(db, _provider()).handle_tpay_notification(body, sign_jws(body))

        assert ok is True
        token = next(c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], PaymentToken))
        assert token.kind == TokenKind.BLIK_ALIAS_UID

    async def test_alias_unknown_to_tenant_warning_skipped(self):
        """AC3: brak dopasowania aliasu do tenanta → warning (nie 500), skipped, TRUE."""
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # RLS
                _exec_scalar(None),  # dedup
                _exec_scalar(None),  # brak transakcji rejestracji
            ]
        )
        body = build_alias_notification(event="ALIAS_EXPIRED", alias_value="tg-nieznany")

        ok, status = await WebhookProcessor(db, _provider()).handle_tpay_notification(body, sign_jws(body))

        assert (ok, status) == (True, WebhookProcessingStatus.SKIPPED.value)
        event = db.add.call_args.args[0]
        assert isinstance(event, WebhookEvent)
        assert event.processing_status == WebhookProcessingStatus.SKIPPED.value

    async def test_alias_unregister_updates_token_deleted(self):
        """AC3: ALIAS_UNREGISTER → tpay_status DELETED."""
        txn = _alias_registration_txn("tg-x")
        token = _blik_alias_token(txn.tenant_id, "tg-x")
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),
                _exec_scalar(None),  # dedup zdarzenia
                _exec_scalar(txn),  # transakcja rejestracji
                _exec_scalar(token),  # token po digest
                _exec_scalar(None),  # subskrypcja (update_blik_alias_status, DELETED)
                _exec_scalar(None),  # subskrypcja (notify Ownera) — brak → bez emaila
            ]
        )
        body = build_alias_notification(event="ALIAS_UNREGISTER", alias_value="tg-x")

        ok, status = await WebhookProcessor(db, _provider()).handle_tpay_notification(body, sign_jws(body))

        assert (ok, status) == (True, WebhookProcessingStatus.PROCESSED.value)
        assert token.tpay_status == TpayTokenStatus.DELETED

    async def test_alias_expired_suspended_and_owner_notified(self):
        """AC3: ALIAS_EXPIRED przy aktywnej subskrypcji cyklicznej → SUSPENDED + email Ownera."""
        txn = _alias_registration_txn("tg-exp")
        token = _blik_alias_token(txn.tenant_id, "tg-exp")
        subscription = _active_subscription(txn.tenant_id)
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),
                _exec_scalar(None),  # dedup
                _exec_scalar(txn),  # rejestracja
                _exec_scalar(token),  # token
                _exec_scalar(subscription),  # aktywna subskrypcja cykliczna
            ]
        )
        body = build_alias_notification(event="ALIAS_EXPIRED", alias_value="tg-exp")

        import app.services.billing.webhook_processor as wp

        sent: list[tuple] = []
        original = wp.send_payment_method_expired_email

        def fake_email(email: str, method: str) -> None:
            sent.append((email, method))

        wp.send_payment_method_expired_email = fake_email
        try:
            ok, status = await WebhookProcessor(db, _provider()).handle_tpay_notification(body, sign_jws(body))
        finally:
            wp.send_payment_method_expired_email = original

        assert (ok, status) == (True, WebhookProcessingStatus.PROCESSED.value)
        assert token.tpay_status == TpayTokenStatus.SUSPENDED
        assert sent == [("owner@test.com", "alias BLIK")]

    async def test_alias_update_refreshes_expiration(self):
        """AC3: ALIAS_UPDATE → ACTIVE + odświeżone expires_at."""
        txn = _alias_registration_txn("tg-upd")
        token = _blik_alias_token(txn.tenant_id, "tg-upd")
        token.expires_at = datetime(2027, 1, 1, tzinfo=UTC)
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),
                _exec_scalar(None),
                _exec_scalar(txn),
                _exec_scalar(token),
                _exec_scalar(None),  # subskrypcja — brak
            ]
        )
        body = build_alias_notification(event="ALIAS_UPDATE", alias_value="tg-upd", expiration="2029-12-31")

        ok, _ = await WebhookProcessor(db, _provider()).handle_tpay_notification(body, sign_jws(body))

        assert ok is True
        assert token.tpay_status == TpayTokenStatus.ACTIVE
        assert token.expires_at is not None and token.expires_at.year == 2029

    async def test_alias_duplicate_event_uid_skipped(self):
        """AC4: ponowienie przetworzonej notyfikacji aliasu → pominięte, TRUE."""
        existing = WebhookEvent(
            event_uid="alias:ALIAS_REGISTER:tg-dup",
            processing_status=WebhookProcessingStatus.PROCESSED.value,
            raw={},
        )
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[MagicMock(), _exec_scalar(existing)])
        body = build_alias_notification(event="ALIAS_REGISTER", alias_value="tg-dup")

        ok, status = await WebhookProcessor(db, _provider()).handle_tpay_notification(body, sign_jws(body))

        assert (ok, status) == (True, WebhookProcessingStatus.DUPLICATE.value)
        db.add.assert_not_called()

    async def test_alias_without_value_rejected_payload(self):
        """AC5: zwalidowany podpis, śmieciowy payload znanego typu → 400 bez ponowień."""
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[MagicMock(), _exec_scalar(None)])
        # ALIAS_* bez msg_value[value]
        body = b"id=1010-test&event=ALIAS_REGISTER"

        ok, status = await WebhookProcessor(db, _provider()).handle_tpay_notification(body, sign_jws(body))

        assert ok is False
        assert status == WebhookProcessingStatus.REJECTED_PAYLOAD.value
        event = db.add.call_args.args[0]
        assert event.processing_status == WebhookProcessingStatus.REJECTED_PAYLOAD.value
        assert event.error_message


class TestTokenizationDispatch:
    """AC2 — JSON notyfikacje tokenizacyjne (data.token, współpraca 7.2)."""

    async def test_tokenization_saved_via_72_service(self):
        """data.token + cliAuth → PENDING→ACTIVE po registration_id (7.2 AC2)."""
        tenant_id = uuid.uuid4()
        pending = PaymentToken(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            kind=TokenKind.CARD_TOKEN,
            tpay_status=TpayTokenStatus.PENDING,
            registration_id="reg-cli-auth-1",
        )
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # RLS
                _exec_scalar(None),  # dedup zdarzenia
                _exec_scalar(pending),  # PENDING po registration_id (korelacja tenanta)
                _exec_scalar(pending),  # wewnątrz save_card_token_from_notification (7.2)
            ]
        )
        body = build_tokenization_notification(cli_auth="reg-cli-auth-1", token="tbe_newtoken123")

        ok, status = await WebhookProcessor(db, _provider()).handle_tpay_notification(body, sign_jws(body))

        assert (ok, status) == (True, WebhookProcessingStatus.PROCESSED.value)
        assert pending.tpay_status == TpayTokenStatus.ACTIVE
        assert pending.value_digest  # zapisana wartość (digest)
        assert pending.card_tail == "1111"
        assert pending.card_brand == "Mastercard"
        assert pending.expires_at is not None and pending.expires_at.year == 2028
        event = next(c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], WebhookEvent))
        assert event.type == "tokenization"
        assert event.event_uid == "tokenization:tbe_newtoken123"

    async def test_tokenization_without_registration_skipped(self):
        """Brak cliAuth/bez dopasowania → warning + skipped (nie 500, TRUE)."""
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),
                _exec_scalar(None),  # dedup
                _exec_scalar(None),  # brak PENDING po registration_id
            ]
        )
        body = build_tokenization_notification(cli_auth=None)

        ok, status = await WebhookProcessor(db, _provider()).handle_tpay_notification(body, sign_jws(body))

        assert (ok, status) == (True, WebhookProcessingStatus.SKIPPED.value)

    async def test_unknown_json_type_skipped_with_true(self):
        """AC2: nieobsługiwany typ JSON → INFO + skipped, odpowiedź TRUE."""
        import json

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[MagicMock(), _exec_scalar(None)])
        body = json.dumps({"type": "marketplace_transaction", "data": {"x": 1}}).encode()

        ok, status = await WebhookProcessor(db, _provider()).handle_tpay_notification(body, sign_jws(body))

        assert (ok, status) == (True, WebhookProcessingStatus.SKIPPED.value)

    async def test_unknown_form_payload_skipped(self):
        """Form bez tr_id i bez event → nieobsługiwany → skipped + TRUE."""
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[MagicMock(), _exec_scalar(None)])
        body = b"foo=bar&baz=qux"

        ok, status = await WebhookProcessor(db, _provider()).handle_tpay_notification(body, sign_jws(body))

        assert (ok, status) == (True, WebhookProcessingStatus.SKIPPED.value)


class TestTransactionPathUntouched:
    """AC2 — transakcje form (tr_id) wciąż idą logiką 7.4."""

    async def test_transaction_still_processed(self):
        from app.models.subscription_plan import PlanName, SubscriptionPlan

        txn = _alias_registration_txn("tg-abc")  # ma meta plan/payer — wystarczy
        plan = SubscriptionPlan(id=uuid.uuid4(), name=PlanName.BASIC, display_name="Basic")
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # RLS
                _exec_scalar(None),  # dedup
                _exec_scalar(txn),  # korelacja tr_crc
                _exec_scalar(plan),  # plan basic (aktywacja)
                _exec_scalar(None),  # subskrypcja — brak (nowa)
                MagicMock(),  # UPDATE tenants.plan
            ]
        )
        body = build_notification(tr_crc="ord-alias-1", tr_paid=None)

        ok, status = await WebhookProcessor(db, _provider()).handle_tpay_notification(body, sign_jws(body))

        assert (ok, status) == (True, WebhookProcessingStatus.PROCESSED.value)
        assert txn.status == PaymentStatus.PAID


class TestErrorSemantics:
    """AC5 — wyjątek przetwarzania → audyt ERROR + error_message, re-raise (route → 5xx)."""

    async def test_processing_exception_audited_and_raised(self):
        txn = _alias_registration_txn("tg-err")
        token = _blik_alias_token(txn.tenant_id, "tg-err")
        db = AsyncMock()
        # subskrypcja zapytanie wywala (baza niedostępna w trakcie przetwarzania)
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),
                _exec_scalar(None),
                _exec_scalar(txn),
                _exec_scalar(token),
                RuntimeError("db down"),
            ]
        )
        db.flush = AsyncMock(side_effect=[None, None, None, None])
        body = build_alias_notification(event="ALIAS_EXPIRED", alias_value="tg-err")

        processor = WebhookProcessor(db, _provider())
        with pytest.raises(RuntimeError, match="db down"):
            await processor.handle_tpay_notification(body, sign_jws(body))

        # audyt z ERROR + error_message zapisany przed re-raise
        event = db.add.call_args.args[0]
        assert isinstance(event, WebhookEvent)
        assert event.processing_status == WebhookProcessingStatus.ERROR.value
        assert "db down" in (event.error_message or "")


class TestMetrics:
    """AC6 (Task 4.1) — każde przetworzenie zasila metryki Prometheus."""

    async def test_success_observed(self):
        from app.services.billing import webhook_metrics

        webhook_metrics.reset()
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),
                _exec_scalar(None),  # dedup
                _exec_scalar(None),  # brak transakcji rejestracji → skipped
            ]
        )
        body = build_alias_notification(event="ALIAS_EXPIRED", alias_value="tg-m")

        await WebhookProcessor(db, _provider()).handle_tpay_notification(body, sign_jws(body))

        snap = webhook_metrics.snapshot()
        assert snap["skipped"] == 1  # alias bez dopasowania → skipped
        assert snap["last_success_age_seconds"] is None  # brak sukcesu biznesowego

    async def test_processed_updates_last_success(self):
        from app.services.billing import webhook_metrics

        webhook_metrics.reset()
        txn = _alias_registration_txn("tg-ok")
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),
                _exec_scalar(None),
                _exec_scalar(txn),
                _exec_scalar(None),
                _exec_scalar(None),
            ]
        )
        body = build_alias_notification(event="ALIAS_REGISTER", alias_value="tg-ok")

        await WebhookProcessor(db, _provider()).handle_tpay_notification(body, sign_jws(body))

        snap = webhook_metrics.snapshot()
        assert snap["processed"] == 1
        assert snap["last_success_age_seconds"] is not None
        assert snap["consecutive_failures"] == 0

    async def test_error_increments_consecutive_failures(self):
        from app.services.billing import webhook_metrics

        webhook_metrics.reset()
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),
                _exec_scalar(None),
                RuntimeError("boom"),  # lookup transakcji pada
            ]
        )
        db.flush = AsyncMock()
        body = build_alias_notification(event="ALIAS_EXPIRED", alias_value="tg-f")

        processor = WebhookProcessor(db, _provider())
        with pytest.raises(RuntimeError):
            await processor.handle_tpay_notification(body, sign_jws(body))

        snap = webhook_metrics.snapshot()
        assert snap["failed"] == 1
        assert snap["consecutive_failures"] == 1
        assert snap["alert"] is False  # alert dopiero >3

    async def test_alert_after_more_than_three_consecutive_failures(self):
        from app.services.billing import webhook_metrics

        webhook_metrics.reset()
        for _ in range(4):
            webhook_metrics.observe("tpay", "alias", WebhookProcessingStatus.ERROR.value, 0.01)

        snap = webhook_metrics.snapshot()
        assert snap["consecutive_failures"] == 4
        assert snap["alert"] is True

        # sukces resetuje serię
        webhook_metrics.observe("tpay", "alias", WebhookProcessingStatus.PROCESSED.value, 0.01)
        assert webhook_metrics.snapshot()["alert"] is False


class TestInvoiceSavepoint:
    """Fix 2026-09-14 (sandbox live): porażka faktury nie zatruwa transakcji
    webhooka — w PG po nieudanym statement transakcja jest aborted i commit
    aktywacji planu padał (mail potwierdzenia wyszedł, całość wycofana)."""

    async def test_invoice_failure_isolated_by_savepoint(self):
        """generate_invoice rzuca → wyjątek połknięty + wywołanie w begin_nested."""
        db = AsyncMock()
        db.begin_nested = MagicMock(return_value=savepoint_cm())
        txn = _alias_registration_txn("tg-savepoint")
        with patch("app.services.billing.webhook_processor.InvoiceService") as svc:
            svc.return_value.generate_invoice = AsyncMock(side_effect=RuntimeError("boom"))

            await WebhookProcessor(db, _provider())._generate_invoice_safely(txn)  # nie rzuca

        db.begin_nested.assert_called_once()

    async def test_invoice_success_delays_pdf_task(self):
        """Ścieżka szczęśliwa: faktura w savepoincie + enqueue taska PDF."""
        db = AsyncMock()
        db.begin_nested = MagicMock(return_value=savepoint_cm())
        txn = _alias_registration_txn("tg-ok")
        invoice = MagicMock(id=uuid.uuid4())
        with (
            patch("app.services.billing.webhook_processor.InvoiceService") as svc,
            patch("app.workers.tasks.generate_invoice_pdf.generate_invoice_pdf") as pdf_task,
        ):
            svc.return_value.generate_invoice = AsyncMock(return_value=invoice)

            await WebhookProcessor(db, _provider())._generate_invoice_safely(txn)

        db.begin_nested.assert_called_once()
        pdf_task.delay.assert_called_once_with(str(invoice.id))
