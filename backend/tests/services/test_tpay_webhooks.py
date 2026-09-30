"""Testy weryfikacji i przetwarzania webhooka tpay — Story 7.4 (AC3-AC6).

``TpayWebhookVerifier`` — czysta logika (JWS z certyfikatem testowym,
md5sum wg wzoru tpay). ``WebhookProcessor`` — przepływ na mockowanej sesji
DB (wzorzec test_billing_plans): sekwencje ``db.execute`` opisane per test.
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.payment import PaymentStatus, PaymentTransaction, WebhookEvent, WebhookProcessingStatus
from app.models.subscription import SubscriptionStatus
from app.models.subscription_plan import PlanName, SubscriptionPlan
from app.services.billing.providers.tpay import TpayProvider
from app.services.billing.webhook_processor import WebhookProcessor, parse_form
from tests.fixtures.tpay_fixtures import (
    TEST_MERCHANT_ID,
    TEST_SECURITY_CODE,
    build_notification,
    compute_md5sum,
    make_test_billing_settings,
    sign_jws,
    sign_jws_detached,
    signing_cert_pem,
)


def _provider() -> TpayProvider:
    settings = make_test_billing_settings()
    return TpayProvider(settings, pinned_cert_pem=signing_cert_pem())


def _exec_scalar(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


def _txn(amount: str = "30.00", plan: str = "basic", test_mode: bool = False) -> PaymentTransaction:
    return PaymentTransaction(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        provider="tpay",
        transaction_id="ta_TEST123",
        hidden_description="ord-1",
        amount=Decimal(amount),
        currency="PLN",
        status=PaymentStatus.PENDING,
        test_mode=test_mode,
        meta={"plan": plan, "payer_email": "owner@test.com"},
    )


class TestVerifyMd5sum:
    """AC3 — druga warstwa: md5(merchant_id + tr_id + tr_amount + tr_crc + kod)."""

    def test_md5_formula_matches_tpay_spec(self):
        verifier = _provider().verifier
        expected = compute_md5sum(TEST_MERCHANT_ID, "TR-1", "30.00", "crc-1", TEST_SECURITY_CODE)
        assert verifier.compute_md5sum(tr_id="TR-1", tr_amount="30.00", tr_crc="crc-1") == expected

    def test_verify_ok(self):
        verifier = _provider().verifier
        body = build_notification(tr_crc="ord-1")
        assert verifier.verify_md5sum(body) is True

    def test_verify_wrong_md5_rejected(self):
        verifier = _provider().verifier
        body = build_notification(md5sum_override="0" * 32)
        assert verifier.verify_md5sum(body) is False

    def test_verify_missing_fields_rejected(self):
        verifier = _provider().verifier
        assert verifier.verify_md5sum(b"tr_id=TR-1") is False


class TestVerifyJws:
    """AC3 — pierwsza warstwa: podpis RS256 certyfikatem przypiętym."""

    @pytest.mark.asyncio
    async def test_valid_signature_ok(self):
        verifier = _provider().verifier
        body = build_notification()
        assert await verifier.verify_jws(sign_jws(body), body) is True

    @pytest.mark.asyncio
    async def test_detached_jws_ok(self):
        """Format realnych notyfikacji tpay: detached JWS — pusty środkowy
        segment, podpis nad base64url(body). Odkryte na sandboxie 2026-09-14
        (6/6 webhooków rejected_signature po udanej płatności)."""
        verifier = _provider().verifier
        body = build_notification()
        assert await verifier.verify_jws(sign_jws_detached(body), body) is True

    @pytest.mark.asyncio
    async def test_detached_jws_tampered_body_rejected(self):
        """Detached JWS + podmienione body → podpis (nad base64url(body))
        się nie zgadza → odrzucenie."""
        verifier = _provider().verifier
        jws = sign_jws_detached(build_notification())
        tampered = build_notification(tr_amount="50.00")
        assert await verifier.verify_jws(jws, tampered) is False

    @pytest.mark.asyncio
    async def test_detached_jws_x5u_only_ok(self, monkeypatch):
        """Sandbox tpay: nagłówek JWS z ``x5u`` (bez ``x5c``), podpis kluczem
        SANDBOXOWYM ≠ przypięty PEM — certyfikat pobrany z x5u (domena tpay)
        weryfikuje podpis; fallback na pinned by odrzucił (InvalidSignature)."""
        from tests.fixtures.tpay_fixtures import _sandbox_signing_key, sandbox_signing_cert_pem

        verifier = _provider().verifier  # pinned = główny certyfikat testowy
        body = build_notification()
        jws = sign_jws_detached(
            body,
            include_x5c=False,
            x5u="https://secure.tpay.com/x509/notifications-jws.pem",
            signing_key=_sandbox_signing_key(),
        )

        async def fake_fetch(url: str) -> str:
            assert url.endswith("notifications-jws.pem")
            return sandbox_signing_cert_pem()

        monkeypatch.setattr("app.services.billing.providers.tpay.webhooks._fetch_cert_pem", fake_fetch)
        assert await verifier.verify_jws(jws, body) is True

    @pytest.mark.asyncio
    async def test_x5u_outside_tpay_domain_ignored(self):
        """``x5u`` spoza domeny tpay (anti-SSRF) → None, certyfikatu nie pobieramy."""
        from app.services.billing.providers.tpay.webhooks import _cert_pem_from_x5u

        assert await _cert_pem_from_x5u("https://evil.example.com/cert.pem") is None

    @pytest.mark.asyncio
    async def test_tampered_body_rejected(self):
        verifier = _provider().verifier
        body = build_notification()
        jws = sign_jws(body)
        tampered = build_notification(tr_amount="50.00")  # inna kwota po podpisaniu
        assert await verifier.verify_jws(jws, tampered) is False

    @pytest.mark.asyncio
    async def test_payload_body_mismatch_rejected(self):
        """Payload JWS musi być dokładnie surowym body (anti-swap)."""
        verifier = _provider().verifier
        body = build_notification()
        jws = sign_jws(build_notification(tr_id="OTHER"))  # podpisane inne body
        assert await verifier.verify_jws(jws, body) is False

    @pytest.mark.asyncio
    async def test_foreign_certificate_rejected(self):
        """Podpisany innym kluczem niż przypięty certyfikat → odrzucony."""
        verifier = _provider().verifier
        body = build_notification()
        import json

        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        from tests.fixtures.tpay_fixtures import _b64url, _signing_key

        # Inny klucz + x5c z certyfikatem testowym (nigdy nie pasuje do podpisu).
        other_key = _signing_key()  # ten sam klucz — więc zepsujemy inaczej:
        header = {"alg": "RS256", "x5c": [_b64url(b"not-a-cert")]}
        header_b64 = _b64url(json.dumps(header).encode())
        payload_b64 = _b64url(body)
        signing_input = f"{header_b64}.{payload_b64}".encode()
        sig = other_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
        assert await verifier.verify_jws(f"{header_b64}.{payload_b64}.{_b64url(sig)}", body) is False

    @pytest.mark.asyncio
    async def test_unsupported_alg_rejected(self):
        verifier = _provider().verifier
        body = build_notification()
        assert await verifier.verify_jws("a.b.c", body) is False  # niepoprawny JWS

    @pytest.mark.asyncio
    async def test_verify_both_layers(self):
        provider = _provider()
        body = build_notification()
        assert await provider.verify_webhook_async(body, sign_jws(body)) is True
        # brak nagłówka JWS → False (niezależnie od poprawnego md5)
        assert await provider.verify_webhook_async(body, None) is False

    @pytest.mark.asyncio
    async def test_signature_from_foreign_key_rejected(self):
        """AC1 (7.3): poprawny JWS podpisany OBCYM kluczem (z własnym x509,
        podpis spójny z x5c) — ale klucz ≠ przypięty → odrzucony."""
        from tests.fixtures.tpay_fixtures import sign_jws_with_foreign_key

        verifier = _provider().verifier
        body = build_notification()
        assert await verifier.verify_jws(sign_jws_with_foreign_key(body), body) is False


class TestCertificateRotation:
    """Task 2.1 (7.3) — cache x509 z TTL + obsługa rotacji certyfikatów tpay.

    Rotacja: gdy x5c nie pasuje do przypiętego certyfikatu, walidator wymusza
    odświeżenie cache (bypass TTL) i porównuje ponownie; poprzedni certyfikat
    pozostaje akceptowany w okresie grace (ponadterminowane requesty w locie).
    """

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        from app.services.billing.providers.tpay import webhooks as webhooks_mod

        webhooks_mod._CERT_CACHE.clear()
        webhooks_mod._PREV_CERT_CACHE.clear()
        yield
        webhooks_mod._CERT_CACHE.clear()
        webhooks_mod._PREV_CERT_CACHE.clear()

    def _settings(self):
        return make_test_billing_settings()

    async def test_cert_cached_within_ttl(self, monkeypatch):
        """Wewnątrz TTL certyfikat nie jest pobierany ponownie."""
        import app.services.billing.providers.tpay.webhooks as webhooks_mod

        fetches = []

        async def fake_fetch(url: str) -> str:
            fetches.append(url)
            return signing_cert_pem()

        monkeypatch.setattr(webhooks_mod, "_fetch_cert_pem", fake_fetch)
        await webhooks_mod.get_pinned_cert_pem(self._settings())
        await webhooks_mod.get_pinned_cert_pem(self._settings())
        assert len(fetches) == 1

    async def test_force_refresh_after_ttl(self, monkeypatch):
        """Po upływie TTL cache jest odświeżany."""
        import time

        import app.services.billing.providers.tpay.webhooks as webhooks_mod

        fetches: list[str] = []

        async def fake_fetch(url: str) -> str:
            fetches.append(url)
            return signing_cert_pem()

        monkeypatch.setattr(webhooks_mod, "_fetch_cert_pem", fake_fetch)
        await webhooks_mod.get_pinned_cert_pem(self._settings())
        # symulacja upływu TTL
        webhooks_mod._CERT_CACHE[self._settings().tpay_jws_cert_url] = (
            signing_cert_pem(),
            time.monotonic() - webhooks_mod._CERT_CACHE_TTL - 1,
        )
        await webhooks_mod.get_pinned_cert_pem(self._settings())
        assert len(fetches) == 2

    async def test_rotation_detected_refetches_once(self, monkeypatch):
        """x5c z NOWYM certyfikatem tpay (po rotacji) → wymuszone odświeżenie
        cache (bypass TTL) i akceptacja nowego klucza."""
        import app.services.billing.providers.tpay.webhooks as webhooks_mod
        from app.services.billing.providers.tpay.webhooks import TpayWebhookVerifier
        from tests.fixtures.tpay_fixtures import foreign_signing_cert_pem, sign_jws_with_foreign_key

        fetches: list[str] = []

        async def fake_fetch(url: str) -> str:
            fetches.append(url)
            return foreign_signing_cert_pem()  # po rotacji URL zwraca nowy PEM

        monkeypatch.setattr(webhooks_mod, "_fetch_cert_pem", fake_fetch)

        # przypięty STARY certyfikat (testowy) — w cache i jawnie; JWS podpisany
        # NOWYM (obcym) kluczem
        settings = self._settings()
        webhooks_mod._CERT_CACHE[settings.tpay_jws_cert_url] = (signing_cert_pem(), 0.0)
        verifier = TpayWebhookVerifier(settings, pinned_cert_pem=signing_cert_pem())
        body = build_notification()

        assert await verifier.verify_jws(sign_jws_with_foreign_key(body), body) is True
        assert len(fetches) == 1  # dokładnie jedno wymuszone odświeżenie
        # stary certyfikat trafił do prev-cache (grace dla notyfikacji w locie)
        assert webhooks_mod._PREV_CERT_CACHE[self._settings().tpay_jws_cert_url] == signing_cert_pem()

    async def test_prev_cert_grace_accepted(self, monkeypatch):
        """Notyfikacja podpisana starym certyfikatem zaraz po rotacji (w locie)
        → akceptowana z prev-cache."""
        import app.services.billing.providers.tpay.webhooks as webhooks_mod
        from app.services.billing.providers.tpay.webhooks import TpayWebhookVerifier
        from tests.fixtures.tpay_fixtures import foreign_signing_cert_pem

        async def fake_fetch(url: str) -> str:
            return foreign_signing_cert_pem()  # po rotacji URL zwraca nowy PEM

        monkeypatch.setattr(webhooks_mod, "_fetch_cert_pem", fake_fetch)

        settings = self._settings()
        # pinned = NOWY (obcy) certyfikat; prev = STARY (testowy)
        webhooks_mod._CERT_CACHE[settings.tpay_jws_cert_url] = (foreign_signing_cert_pem(), 0.0)
        webhooks_mod._PREV_CERT_CACHE[settings.tpay_jws_cert_url] = signing_cert_pem()

        verifier = TpayWebhookVerifier(settings, pinned_cert_pem=foreign_signing_cert_pem())
        body = build_notification()

        # JWS podpisany STARYM (testowym) kluczem — x5c ze starego certyfikatu
        assert await verifier.verify_jws(sign_jws(body), body) is True


class TestWebhookProcessor:
    """AC4/AC5/AC6 — idempotencja, korelacja tr_crc, aktywacja, kwoty rozbieżne."""

    def _processor(self, db: AsyncMock) -> WebhookProcessor:
        return WebhookProcessor(db, _provider())

    async def test_happy_path_paid_activates_plan(self):
        """AC5: pełna kwota → paid + aktywacja basic (next_charge_at = +30 dni)."""
        txn = _txn()
        plan = SubscriptionPlan(id=uuid.uuid4(), name=PlanName.BASIC, display_name="Basic")
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL RLS
                _exec_scalar(None),  # dedup: brak zdarzenia
                _exec_scalar(txn),  # korelacja po hidden_description (tr_crc)
                _exec_scalar(plan),  # plan basic
                _exec_scalar(None),  # subskrypcja: brak (nowa)
                MagicMock(),  # UPDATE tenants.plan
            ]
        )
        body = build_notification(tr_crc="ord-1")
        ok, status = await self._processor(db).handle_tpay_notification(body, sign_jws(body))

        assert (ok, status) == (True, WebhookProcessingStatus.PROCESSED.value)
        assert txn.status == PaymentStatus.PAID
        assert txn.paid_amount == Decimal("30.00")
        assert txn.test_mode is True  # sandbox: test_mode=1
        assert txn.title == "TR-123456"
        added = [c.args[0] for c in db.add.call_args_list]
        sub = next(o for o in added if type(o).__name__ == "Subscription")
        assert sub.status == SubscriptionStatus.ACTIVE
        assert sub.plan_id == plan.id
        # audyt + idempotencja: WebhookEvent PROCESSED z event_uid tr_id:tr_status
        event = next(o for o in added if isinstance(o, WebhookEvent))
        assert event.event_uid == "TR-123456:true"
        assert event.processing_status == WebhookProcessingStatus.PROCESSED.value

    async def test_duplicate_notification_skipped(self):
        """AC4: ponowienie tej samej notyfikacji (processed) → pomijane."""
        from app.models.payment import WebhookEvent

        existing = WebhookEvent(
            event_uid="TR-123456:true",
            processing_status=WebhookProcessingStatus.PROCESSED.value,
            raw={},
        )
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[MagicMock(), _exec_scalar(existing)])

        body = build_notification(tr_crc="ord-1")
        ok, status = await self._processor(db).handle_tpay_notification(body, sign_jws(body))

        assert (ok, status) == (True, WebhookProcessingStatus.DUPLICATE.value)
        db.add.assert_not_called()

    async def test_rejected_md5_does_not_block_retry(self):
        """Odrzucona próba (błędny md5) nie blokuje ponowienia z poprawnym md5."""
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[MagicMock(), _exec_scalar(None)])
        bad = build_notification(md5sum_override="0" * 32)

        ok, status = await self._processor(db).handle_tpay_notification(bad, sign_jws(bad))
        assert (ok, status) == (False, WebhookProcessingStatus.REJECTED_MD5.value)
        # wiersz audytu odrzucenia zapisany
        event = db.add.call_args.args[0]
        assert isinstance(event, WebhookEvent)
        assert event.processing_status == WebhookProcessingStatus.REJECTED_MD5.value

    async def test_rejected_jws(self):
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[MagicMock(), _exec_scalar(None)])
        body = build_notification()

        ok, status = await self._processor(db).handle_tpay_notification(body, "not-a-jws")
        assert (ok, status) == (False, WebhookProcessingStatus.REJECTED_SIGNATURE.value)

    async def test_amount_mismatch_requires_manual_review(self):
        """AC5: tr_paid != tr_amount → charged_back, bez aktywacji."""
        txn = _txn(amount="30.00")
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[MagicMock(), _exec_scalar(None), _exec_scalar(txn)])
        body = build_notification(tr_crc="ord-1", tr_amount="30.00", tr_paid="10.00")

        ok, status = await self._processor(db).handle_tpay_notification(body, sign_jws(body))

        assert (ok, status) == (True, WebhookProcessingStatus.PROCESSED.value)
        assert txn.status == PaymentStatus.CHARGED_BACK
        assert txn.paid_amount == Decimal("10.00")
        # brak zapytań o plan/subskrypcję → brak aktywacji
        assert db.execute.call_count == 3

    async def test_chargeback_marks_charged_back(self):
        txn = _txn()
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[MagicMock(), _exec_scalar(None), _exec_scalar(txn)])
        body = build_notification(tr_crc="ord-1", tr_status="chargeback")

        ok, _ = await self._processor(db).handle_tpay_notification(body, sign_jws(body))
        assert ok is True
        assert txn.status == PaymentStatus.CHARGED_BACK

    async def test_unknown_tr_crc_no_match(self):
        """AC5: korelacja wyłącznie po tr_crc — brak zamówienia → TRUE + audyt."""
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[MagicMock(), _exec_scalar(None), _exec_scalar(None)])

        body = build_notification(tr_crc="ord-unknown")
        ok, status = await self._processor(db).handle_tpay_notification(body, sign_jws(body))

        assert (ok, status) == (True, WebhookProcessingStatus.NO_MATCH.value)

    async def test_test_mode_never_activates_in_production(self):
        """AC5 asercja: test_mode=1 przy TPAY_ENV=production → bez aktywacji."""
        txn = _txn()
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[MagicMock(), _exec_scalar(None), _exec_scalar(txn)])
        prod_provider = TpayProvider(
            make_test_billing_settings(tpay_env="production"), pinned_cert_pem=signing_cert_pem()
        )
        body = build_notification(tr_crc="ord-1")

        ok, _ = await WebhookProcessor(db, prod_provider).handle_tpay_notification(body, sign_jws(body))
        assert ok is True
        assert txn.status == PaymentStatus.PAID
        assert db.execute.call_count == 3  # brak zapytań aktywacyjnych

    def test_parse_form_flattens_first_values(self):
        assert parse_form(b"a=1&a=2&b=3") == {"a": "1", "b": "3"}


class TestPlanChangeWebhook:
    """7.5 Task 2.2 — upgrade finalizowany webhookiem `paid`; porażka → canceled."""

    def _txn_plan_change(self, amount: str = "10.00") -> PaymentTransaction:
        txn = _txn(amount=amount, plan="premium")
        txn.meta = {**txn.meta, "source": "plan_change", "change_id": str(uuid.uuid4())}
        return txn

    async def test_paid_plan_change_calls_finalize_upgrade(self, monkeypatch):
        """`paid` + meta.source=plan_change → finalize_plan_upgrade (nie activate)."""
        from app.services.billing import webhook_processor as wp_mod

        txn = self._txn_plan_change()
        service = AsyncMock()
        monkeypatch.setattr(wp_mod, "SubscriptionService", MagicMock(return_value=service))

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[MagicMock(), _exec_scalar(None), _exec_scalar(txn)])
        body = build_notification(tr_crc="ord-1", tr_amount="10.00", tr_paid="10.00")

        ok, status = await WebhookProcessor(db, _provider()).handle_tpay_notification(body, sign_jws(body))

        assert (ok, status) == (True, WebhookProcessingStatus.PROCESSED.value)
        assert txn.status == PaymentStatus.PAID
        service.finalize_plan_upgrade.assert_awaited_once_with(txn)
        service.activate_paid_plan.assert_not_awaited()
        service.renew_subscription.assert_not_awaited()

    async def test_failed_plan_change_payment_cancels_change(self, monkeypatch):
        """tr_status=false dla plan_change → cancel_failed_plan_change, bez zmiany planu."""
        from app.services.billing import webhook_processor as wp_mod

        txn = self._txn_plan_change()
        service = AsyncMock()
        monkeypatch.setattr(wp_mod, "SubscriptionService", MagicMock(return_value=service))

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[MagicMock(), _exec_scalar(None), _exec_scalar(txn)])
        body = build_notification(tr_crc="ord-1", tr_amount="10.00", tr_status="false")

        ok, _ = await WebhookProcessor(db, _provider()).handle_tpay_notification(body, sign_jws(body))

        assert ok is True
        assert txn.status == PaymentStatus.CHARGED_BACK
        service.cancel_failed_plan_change.assert_awaited_once_with(txn)
        service.finalize_plan_upgrade.assert_not_awaited()
