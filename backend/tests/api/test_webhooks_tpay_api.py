"""Testy kontraktowe API webhooka tpay — Story 7.3 (AC5, Task 3.2).

Semantyka odpowiedzi: 200 ``TRUE``/``{"result":true}`` (sukces/pomijanie),
400 przy błędzie walidacji (bez ponowień), 5xx przy wyjątku przetwarzania
(tpay ponawia). DB mockowana (wzorzec test_billing_payment_methods).
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_db, get_payment_provider
from app.main import create_app
from app.models.payment import PaymentStatus, PaymentTransaction
from app.services.billing.providers.tpay import TpayProvider
from tests.fixtures.tpay_fixtures import (
    build_alias_notification,
    build_notification,
    build_tokenization_notification,
    make_test_billing_settings,
    sign_jws,
    signing_cert_pem,
)


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _provider() -> TpayProvider:
    return TpayProvider(make_test_billing_settings(), pinned_cert_pem=signing_cert_pem())


def _override(app, db: AsyncMock) -> None:
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_payment_provider] = lambda: _provider()


def _exec_scalar(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


def _alias_txn(alias_value: str) -> PaymentTransaction:
    return PaymentTransaction(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        provider="tpay",
        hidden_description="ord-1",
        amount=Decimal("30.00"),
        currency="PLN",
        status=PaymentStatus.PAID,
        meta={"plan": "basic", "payer_email": "o@t.pl", "blik_alias_value": alias_value},
    )


class TestResponseSemantics:
    """AC5 — macierz statusów odpowiedzi."""

    async def test_form_success_true_200(self, client, app):
        """Sukces transakcji → 200 + body TRUE (text/plain)."""
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),
                _exec_scalar(None),  # dedup
                _exec_scalar(None),  # brak zamówienia → no_match (TRUE)
            ]
        )
        _override(app, db)
        body = build_notification(tr_crc="ord-x")

        resp = await client.post(
            "/api/v1/billing/webhooks/tpay",
            content=body,
            headers={"Content-Type": "application/x-www-form-urlencoded", "X-JWS-Signature": sign_jws(body)},
        )

        assert resp.status_code == 200
        assert resp.text == "TRUE"

    async def test_json_tokenization_result_true_200(self, client, app):
        """Notyfikacja JSON → 200 + {"result": true} (oczekiwane przez tpay)."""
        from app.models.payment import PaymentToken, TpayTokenStatus

        pending = PaymentToken(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            kind="card_token",
            tpay_status=TpayTokenStatus.PENDING,
            registration_id="reg-1",
        )
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),
                _exec_scalar(None),  # dedup
                _exec_scalar(pending),  # PENDING po registration_id
                _exec_scalar(pending),  # wewnątrz serwisu 7.2
            ]
        )
        _override(app, db)
        body = build_tokenization_notification(cli_auth="reg-1")

        resp = await client.post(
            "/api/v1/billing/webhooks/tpay",
            content=body,
            headers={"Content-Type": "application/json", "X-JWS-Signature": sign_jws(body)},
        )

        assert resp.status_code == 200
        assert resp.json() == {"result": True}

    async def test_bad_signature_400_false(self, client, app):
        """AC1: nieprawidłowy podpis → 400 + FALSE (bez ponowień)."""
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[MagicMock(), _exec_scalar(None)])
        _override(app, db)
        body = build_notification()

        resp = await client.post(
            "/api/v1/billing/webhooks/tpay",
            content=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-JWS-Signature": "not-a-jws",
            },
        )

        assert resp.status_code == 400
        assert resp.text == "FALSE"
        # wpis audytu odrzucenia utrwalony (commit przy 400)
        db.commit.assert_awaited()

    async def test_missing_jws_header_400(self, client, app):
        """AC1: brak nagłówka X-JWS-Signature → 400."""
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[MagicMock(), _exec_scalar(None)])
        _override(app, db)
        body = build_notification()

        resp = await client.post(
            "/api/v1/billing/webhooks/tpay",
            content=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        assert resp.status_code == 400

    async def test_processing_exception_500(self, client, app):
        """AC5: wyjątek (baza niedostępna w trakcie) → 5xx — tpay ponowi."""
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),
                _exec_scalar(None),  # dedup
                RuntimeError("db down"),  # lookup transakcji rejestracji pada
            ]
        )
        _override(app, db)
        body = build_alias_notification(event="ALIAS_EXPIRED", alias_value="tg-x")

        resp = await client.post(
            "/api/v1/billing/webhooks/tpay",
            content=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-JWS-Signature": sign_jws(body),
            },
        )

        assert resp.status_code == 500
        assert resp.text == "FALSE"
        # best-effort commit audytu error
        db.commit.assert_awaited()

    async def test_alias_flow_via_api(self, client, app):
        """AC3 e2e: ALIAS_REGISTER z dopasowaniem → 200 TRUE."""
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),
                _exec_scalar(None),
                _exec_scalar(_alias_txn("tg-api")),
                _exec_scalar(None),  # dedup tokenu
                _exec_scalar(None),  # subskrypcja (_link_default_method)
            ]
        )
        _override(app, db)
        body = build_alias_notification(event="ALIAS_REGISTER", alias_value="tg-api")

        resp = await client.post(
            "/api/v1/billing/webhooks/tpay",
            content=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-JWS-Signature": sign_jws(body),
            },
        )

        assert resp.status_code == 200
        assert resp.text == "TRUE"


class TestWebhookHealthEndpoint:
    """AC6 (Task 4.3) — health webhooków: liczniki + wiek ostatniego sukcesu."""

    def _override_admin(self, app, *, role: str = "admin"):
        from fastapi import Request

        from app.core.dependencies import get_current_user
        from tests.factories import make_user

        user = make_user()
        tenant_id = uuid.uuid4()
        user._tenant_id = tenant_id

        async def override_user(request: Request):
            request.state.user = user
            request.state.tenant_id = tenant_id
            request.state.role = role
            request.state.is_admin = role == "admin"
            return user

        app.dependency_overrides[get_current_user] = override_user

    async def test_admin_gets_health_snapshot(self, client, app):
        from app.services.billing import webhook_metrics

        webhook_metrics.reset()
        webhook_metrics.observe("tpay", "transaction", "processed", 0.01)
        self._override_admin(app)

        resp = await client.get("/api/v1/billing/webhooks/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["processed"] >= 1
        assert body["last_success_age_seconds"] is not None
        assert "consecutive_failures" in body and "alert" in body

    async def test_non_admin_forbidden(self, client, app):
        self._override_admin(app, role="owner")

        resp = await client.get("/api/v1/billing/webhooks/health")

        assert resp.status_code == 403

    async def test_metrics_endpoint_mounted(self, client, app):
        """/metrics (Prometheus) eksponuje liczniki webhooków."""
        from app.services.billing import webhook_metrics

        webhook_metrics.observe("tpay", "alias", "processed", 0.02)

        # mount Starlette: /metrics → 307 na /metrics/ (scraper Prometheusa
        # podąża za redirectem; httpx domyślnie nie).
        resp = await client.get("/metrics", follow_redirects=True)

        assert resp.status_code == 200
        assert "webhook_processed_total" in resp.text
        assert "webhook_processing_seconds" in resp.text
