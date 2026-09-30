"""Testy replay notyfikacji webhooka — Story 7.3 (AC7, Task 6.4).

Unit: odtworzenie raw body, pominięta walidacja, idempotencja biznesowa,
blokada zdarzeń odrzuconych. API: uprawnienia (tylko Admin), audyt operacji,
odpowiedź. DB mockowana (wzorzec test_billing_payment_methods).
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import ConflictError
from app.main import create_app
from app.models.payment import PaymentTransaction, WebhookEvent, WebhookProcessingStatus
from app.services.billing.providers.tpay import TpayProvider
from app.services.billing.webhook_processor import WebhookProcessor
from tests.factories import make_user
from tests.fixtures.tpay_fixtures import make_test_billing_settings, signing_cert_pem


def _provider() -> TpayProvider:
    return TpayProvider(make_test_billing_settings(), pinned_cert_pem=signing_cert_pem())


def _exec_scalar(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


def _event(
    status: WebhookProcessingStatus = WebhookProcessingStatus.ERROR,
    *,
    type_: str = "alias",
    raw: dict | None = None,
) -> WebhookEvent:
    return WebhookEvent(
        id=uuid.uuid4(),
        event_uid="alias:ALIAS_EXPIRED:tg-replay",
        provider="tpay",
        type=type_,
        raw=raw or {"event": "ALIAS_EXPIRED", "msg_value[value]": "tg-replay"},
        processing_status=status,
    )


class TestReplayUnit:
    """AC7 — replay przez ten sam pipeline, bez walidacji, idempotentny."""

    async def test_replay_reprocesses_failed_alias_event(self):
        """Zdarzenie error → reprocessing (bez JWS!) → processed."""
        txn = PaymentTransaction(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            hidden_description="ord-r",
            amount=Decimal("30.00"),
            meta={"blik_alias_value": "tg-replay", "payer_email": "o@t.pl"},
        )
        from app.models.payment import PaymentToken, TokenKind, TpayTokenStatus
        from app.services.billing.subscription_service import encrypt_token_value, token_digest

        token = PaymentToken(
            id=uuid.uuid4(),
            tenant_id=txn.tenant_id,
            kind=TokenKind.BLIK_ALIAS_PAYID,
            value_encrypted=encrypt_token_value(txn.tenant_id, "tg-replay"),
            value_digest=token_digest(txn.tenant_id, "tg-replay"),
            tpay_status=TpayTokenStatus.ACTIVE,
        )
        event = _event(WebhookProcessingStatus.ERROR)
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # RLS
                _exec_scalar(txn),  # transakcja rejestracji
                _exec_scalar(token),  # token po digest
                _exec_scalar(None),  # subskrypcja — brak → bez powiadomienia
            ]
        )

        ok, status = await WebhookProcessor(db, _provider()).replay_event(event)

        assert (ok, status) == (True, WebhookProcessingStatus.PROCESSED.value)
        assert token.tpay_status == TpayTokenStatus.SUSPENDED  # ALIAS_EXPIRED
        # wiersz audytu zaktualizowany w miejscu (ten sam obiekt)
        assert event.processing_status == WebhookProcessingStatus.PROCESSED.value
        assert event.error_message is None

    async def test_replay_processed_event_is_duplicate_noop(self):
        """AC7: replay zdarzenia processed → DUPLICATE, bez efektów biznesowych."""
        event = _event(WebhookProcessingStatus.PROCESSED)
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[MagicMock()])  # tylko RLS

        ok, status = await WebhookProcessor(db, _provider()).replay_event(event)

        assert (ok, status) == (True, WebhookProcessingStatus.DUPLICATE.value)
        db.add.assert_not_called()

    async def test_replay_rejected_event_forbidden(self):
        """Zdarzenia odrzucone walidacją nie podlegają replayowi (bezpieczeństwo)."""
        event = _event(WebhookProcessingStatus.REJECTED_SIGNATURE)
        db = AsyncMock()

        with pytest.raises(ConflictError):
            await WebhookProcessor(db, _provider()).replay_event(event)

    async def test_reconstruct_raw_tokenization_json(self):
        event = _event(WebhookProcessingStatus.ERROR, type_="tokenization", raw={"type": "tokenization", "data": {}})
        raw = WebhookProcessor._reconstruct_raw(event)
        assert raw.startswith(b"{")  # JSON


class TestReplayApi:
    """AC7/Task 6.4 — uprawnienia (tylko Admin), audyt operacji."""

    @pytest.fixture
    def app(self):
        return create_app()

    @pytest.fixture
    async def client(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    def _override_auth(self, app, db, *, role: str = "admin", is_admin: bool = True):
        from fastapi import Request

        tenant_id = uuid.uuid4()
        user = make_user()
        user._tenant_id = tenant_id

        async def override_user(request: Request):
            request.state.user = user
            request.state.tenant_id = tenant_id
            request.state.role = role
            request.state.is_admin = is_admin
            return user

        async def override_db():
            yield db

        app.dependency_overrides[get_current_user] = override_user
        app.dependency_overrides[get_db] = override_db
        return user, tenant_id

    async def test_admin_replays_event_with_audit(self, client, app):
        """Admin → 200 + zapis w logu audytu admina (kto, kiedy, jaki event)."""
        event = _event(WebhookProcessingStatus.PROCESSED)  # → DUPLICATE (no-op)
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                _exec_scalar(event),  # fetch WebhookEvent po event_uid
                MagicMock(),  # RLS (replay _process)
            ]
        )
        user, _ = self._override_auth(app, db)

        resp = await client.post(f"/api/v1/admin/billing/webhooks/{event.event_uid}/replay")

        assert resp.status_code == 200
        body = resp.json()
        assert body["replayed"] is True
        assert body["processing_status"] == WebhookProcessingStatus.DUPLICATE.value
        # wpis audytu: akcja billing.webhook_replayed, user=admin, NIL tenant
        added = [c.args[0] for c in db.add.call_args_list]
        audit = next(o for o in added if type(o).__name__ == "AuditLog")
        assert audit.action == "billing.webhook_replayed"
        assert audit.user_id == user.id
        assert str(audit.tenant_id) == "00000000-0000-0000-0000-000000000000"
        assert audit.details["event_uid"] == event.event_uid

    async def test_owner_role_forbidden(self, client, app):
        """Tylko Admin — Owner dostaje 403."""
        db = AsyncMock()
        self._override_auth(app, db, role="owner", is_admin=False)

        resp = await client.post("/api/v1/admin/billing/webhooks/whatever/replay")

        assert resp.status_code == 403

    async def test_unknown_event_404(self, client, app):
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_exec_scalar(None)])
        self._override_auth(app, db)

        resp = await client.post("/api/v1/admin/billing/webhooks/nie-ma-takiego/replay")

        assert resp.status_code == 404

    async def test_rejected_event_conflict_409(self, client, app):
        """Zdarzenie rejected_* → 409 (replay niedostępny)."""
        event = _event(WebhookProcessingStatus.REJECTED_MD5)
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_exec_scalar(event)])
        self._override_auth(app, db)

        resp = await client.post(f"/api/v1/admin/billing/webhooks/{event.event_uid}/replay")

        assert resp.status_code == 409
