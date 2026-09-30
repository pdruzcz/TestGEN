"""WebhookProcessor — dispatcher notyfikacji tpay (Stories 7.4 + 7.3).

Macierz typów (7.3 AC2) — klasyfikacja po strukturze payloadu, wszystkie
typy przychodzą na ten sam URL notyfikacji:

- **form-urlencoded (transakcja):** ``tr_id``/``tr_crc``/``tr_status`` —
  logika biznesowa 7.4 (aktywacja/odrzucenie) w :meth:`_handle_transaction`,
- **JSON (tokenizacja):** ``type = tokenization|token_update`` + ``data.token``
  po rejestracji ``POST /tokens`` — zapis tokena przez serwis 7.2,
- **form-urlencoded (alias BLIK):** ``event = ALIAS_REGISTER|ALIAS_UPDATE|
  ALIAS_UNREGISTER|ALIAS_EXPIRED`` + ``msg_value[value]`` — aktualizacja
  ``PaymentToken`` (status/kind/ważność),
- **nieobsługiwane:** INFO + audyt ``skipped``, odpowiedź TRUE (AC2).

Wspólne dla wszystkich typów (7.4 → 7.3): walidacja JWS obowiązkowa
(tpay nie ma whitelisty IP), audyt każdego żądania w ``webhook_events``,
idempotencja po ``event_uid``, wyjątek przetwarzania → audyt ``error`` +
re-raise (endpoint odpowiada 5xx — tpay ponawia; AC5 7.3).

Przepływ bez JWT — kontekst RLS admina (NIL UUID) ustawiany na starcie
(wzorzec auth_service). Status ``test_mode`` z sandboxa nigdy nie aktywuje
planu, gdy aplikacja biegnie na ``TPAY_ENV=production`` (7.4 AC5).
"""

import json
import logging
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import ClassVar
from urllib.parse import parse_qs, urlencode

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config_billing import get_billing_settings
from app.core.constants import NIL_UUID
from app.core.exceptions import ConflictError
from app.models.payment import (
    PaymentStatus,
    PaymentToken,
    PaymentTransaction,
    TokenKind,
    TpayTokenStatus,
    WebhookEvent,
    WebhookProcessingStatus,
)
from app.models.subscription import SubscriptionStatus
from app.models.subscription_plan import PlanName
from app.services.billing import webhook_metrics
from app.services.billing.invoice_service import InvoiceService
from app.services.billing.providers.tpay import TpayProvider
from app.services.billing.subscription_service import SubscriptionService
from app.services.email.email_service import send_payment_method_expired_email

logger = logging.getLogger(__name__)

_REQUIRED_FIELDS = ("tr_id", "tr_amount", "tr_crc", "tr_status", "md5sum")

# Klasyfikacja payloadu (AC2).
KIND_TRANSACTION = "transaction"
KIND_ALIAS = "alias"
KIND_TOKENIZATION = "tokenization"
KIND_UNKNOWN = "unknown"

# Notyfikacje JSON tpay obsługiwane przez handler tokenizacyjny (docs tpay).
_TOKENIZATION_TYPES = {"tokenization", "token_update"}

# Mapowanie eventów aliasów na status tokena (AC3): REGISTER/UPDATE → ACTIVE
# (przy UPDATE odświeżana ważność), UNREGISTER → DELETED (soft delete),
# EXPIRED → SUSPENDED (wymaga akcji płatnika — powiadomienie Ownera).
_ALIAS_STATUS = {
    "ALIAS_REGISTER": TpayTokenStatus.ACTIVE,
    "ALIAS_UPDATE": TpayTokenStatus.ACTIVE,
    "ALIAS_UNREGISTER": TpayTokenStatus.DELETED,
    "ALIAS_EXPIRED": TpayTokenStatus.SUSPENDED,
}


class _Unset:
    """Sentinel — odróżnia „wiersz już odczytany (był None)" od „nie odczytano"."""

    _instance: "ClassVar[_Unset | None]" = None

    def __new__(cls) -> "_Unset":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance


_UNSET = _Unset()


def parse_form(raw_body: bytes) -> dict[str, str]:
    """Form-urlencoded → płaski dict (pierwsza wartość każdego pola)."""
    return {k: v[0] for k, v in parse_qs(raw_body.decode("utf-8", errors="replace")).items()}


def send_payment_method_expired_email_safely(email: str, method: str) -> None:
    """AC3 — powiadomienie Ownera o wygasłej metodzie (best-effort, PL)."""
    try:
        send_payment_method_expired_email(email=email, method=method)
    except Exception:
        logger.warning("Email o wygaśnięciu metody płatności do %s nie wysłany — webhook kontynuuje", email)


class WebhookProcessor:
    def __init__(self, db: AsyncSession, provider: TpayProvider | None = None) -> None:
        self._db = db
        self._provider = provider or TpayProvider(get_billing_settings())

    # --- Dispatcher (AC2) ---

    async def handle_tpay_notification(self, raw_body: bytes, jws_signature: str | None) -> tuple[bool, str]:
        """Klasyfikuje i przetwarza notyfikację. Zwraca ``(ok, processing_status)``.

        ``ok=False`` → endpoint odpowiada 400 (walidacja — AC1/AC5);
        wyjątek przetwarzania biznesowego → audyt ``error`` i **re-raise**
        (endpoint odpowiada 5xx, tpay ponawia — AC5); idempotentne ponowienia
        i notyfikacje bez dopasowania zwracają ``ok=True`` (TRUE przerywa
        serię ponowień tpay — AC4).

        Metryki (AC6/Task 4.1): każde przetworzenie — także odrzucone i
        nieudane — trafia do ``webhook_processed_total`` / ``webhook_processing_seconds``.
        """
        start = time.perf_counter()
        kind, _form, _payload = self._classify(raw_body)
        try:
            ok, status = await self._process(raw_body, jws_signature)
        except Exception:
            webhook_metrics.observe("tpay", kind, WebhookProcessingStatus.ERROR.value, time.perf_counter() - start)
            raise
        webhook_metrics.observe("tpay", kind, status, time.perf_counter() - start)
        return ok, status

    async def replay_event(self, event: WebhookEvent) -> tuple[bool, str]:
        """AC7 — replay zapisanej notyfikacji przez admina.

        Odtwarza surowe body z ``WebhookEvent.raw`` i przepuszcza je przez
        **ten sam pipeline** (klasyfikacja → idempotencja → handlery) z
        pominiętą walidacją podpisu — dane pochodzą z audytu (pierwotnie
        zwalidowane). Idempotencja biznesowa zostaje: zdarzenie już
        ``processed`` nie wywoła efektów ponownie (DUPLICATE).

        Zdarzenia odrzucone walidacją (``rejected_*``) nie podlegają replayowi
        — ich payload nigdy nie przeszedł weryfikacji pochodzenia.
        """
        if str(event.processing_status).startswith("rejected"):
            raise ConflictError(
                f"Replay niedostępny dla zdarzeń odrzuconych walidacją (status={event.processing_status})"
            )

        raw_body = self._reconstruct_raw(event)
        start = time.perf_counter()
        kind, _form, _payload = self._classify(raw_body)
        try:
            ok, status = await self._process(raw_body, None, skip_validation=True, existing_row=event)
        except Exception:
            webhook_metrics.observe("tpay", kind, WebhookProcessingStatus.ERROR.value, time.perf_counter() - start)
            raise
        webhook_metrics.observe("tpay", kind, status, time.perf_counter() - start)
        logger.info(
            "tpay webhook %s: replay przez admina — status %s → %s",
            event.event_uid,
            event.processing_status,
            status,
        )
        return ok, status

    @staticmethod
    def _reconstruct_raw(event: WebhookEvent) -> bytes:
        """Surowe body z zapisanego audytu (JSON dla tokenizacji, form dla pozostałych)."""
        if event.type == KIND_TOKENIZATION:
            return json.dumps(event.raw).encode("utf-8")
        return urlencode(event.raw or {}).encode("utf-8")

    async def _process(
        self,
        raw_body: bytes,
        jws_signature: str | None,
        *,
        skip_validation: bool = False,
        existing_row: WebhookEvent | None | _Unset = _UNSET,
    ) -> tuple[bool, str]:
        """Właściwy pipeline (klasyfikacja → walidacja → idempotencja → handler).

        ``skip_validation`` (replay, AC7): pomija JWS/md5 — dane pochodzą z
        audytu (pierwotnie zwalidowane); ``existing_row`` — wiersz audytu do
        ponownego użycia zamiast fetch po ``event_uid``.
        """
        # Przepływ systemowy (bez JWT) — kontekst admina dla RLS payment_*.
        await self._db.execute(text(f"SET LOCAL app.current_tenant = '{NIL_UUID}'"))

        kind, form, payload = self._classify(raw_body)
        event_uid = self._event_uid(kind, form, payload)
        event_type = (
            KIND_TOKENIZATION if kind == KIND_TOKENIZATION else (KIND_ALIAS if kind == KIND_ALIAS else KIND_TRANSACTION)
        )

        if not skip_validation:
            # Warstwa 1: JWS (X-JWS-Signature) — obowiązkowa dla KAŻDEGO typu
            # notyfikacji (tpay nie ma whitelisty IP; md5 dla aliasów jest
            # deprecated przez tpay, JWS pozostaje jedyną gwarancją pochodzenia).
            if not jws_signature or not await self._provider.verifier.verify_jws(jws_signature, raw_body):
                await self._record_event(
                    event_uid, form or (payload or {}), WebhookProcessingStatus.REJECTED_SIGNATURE, type_=event_type
                )
                logger.warning("tpay webhook %s: odrzucony — nieprawidłowy podpis JWS", event_uid)
                return False, WebhookProcessingStatus.REJECTED_SIGNATURE.value

            # Warstwa 2: md5sum — wyłącznie transakcje (wzór tpay wymaga pól tr_*).
            if kind == KIND_TRANSACTION and not self._provider.verifier.verify_md5sum(raw_body):
                await self._record_event(event_uid, form, WebhookProcessingStatus.REJECTED_MD5, type_=event_type)
                logger.warning("tpay webhook %s: odrzucony — nieprawidłowa suma md5sum", event_uid)
                return False, WebhookProcessingStatus.REJECTED_MD5.value

        # Idempotencja (AC4): tylko notyfikacja już PRZETWORZONA jest pomijana.
        existing = existing_row if not isinstance(existing_row, _Unset) else await self._fetch_event(event_uid)
        if existing is not None and existing.processing_status == WebhookProcessingStatus.PROCESSED:
            logger.info("tpay webhook %s: duplikat — pomijam (idempotencja)", event_uid)
            return True, WebhookProcessingStatus.DUPLICATE.value

        try:
            if kind == KIND_ALIAS:
                return await self._handle_alias(form, event_uid, existing)
            if kind == KIND_TOKENIZATION:
                return await self._handle_tokenization(payload, event_uid, existing)
            if kind == KIND_UNKNOWN:
                # AC2: nieobsługiwany typ — INFO + audyt skipped, TRUE.
                logger.info("tpay webhook %s: nieobsługiwany typ notyfikacji — pomijam", event_uid)
                await self._record_event(
                    event_uid,
                    form or (payload or {}),
                    WebhookProcessingStatus.SKIPPED,
                    type_=event_type,
                    error_message="nieobsługiwany typ notyfikacji",
                    row=existing,
                )
                return True, WebhookProcessingStatus.SKIPPED.value
            return await self._handle_transaction(form, event_uid, existing)
        except Exception as exc:
            # AC5: wyjątek → audyt error + error_message, stack w logach
            # strukturalnych, re-raise (endpoint 5xx → tpay ponawia).
            logger.exception("tpay webhook %s: błąd przetwarzania", event_uid)
            try:
                await self._record_event(
                    event_uid,
                    form or (payload or {}),
                    WebhookProcessingStatus.ERROR,
                    type_=event_type,
                    error_message=str(exc),
                    row=existing,
                )
            except Exception:
                logger.exception("tpay webhook %s: audyt błędu nieosiągalny (DB?)", event_uid)
            raise

    @staticmethod
    def _classify(raw_body: bytes) -> tuple[str, dict[str, str] | None, dict | None]:
        """Rozpoznaje format po strukturze (AC2): JSON ``type`` / form ``event``
        ALIAS_* / form ``tr_id`` / pozostałe → unknown."""
        stripped = raw_body.lstrip()
        if stripped.startswith(b"{"):
            try:
                payload = json.loads(raw_body.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return KIND_UNKNOWN, None, None
            if isinstance(payload, dict) and isinstance(payload.get("type"), str):
                if payload["type"] in _TOKENIZATION_TYPES:
                    return KIND_TOKENIZATION, None, payload
                return KIND_UNKNOWN, None, payload
            return KIND_UNKNOWN, None, payload if isinstance(payload, dict) else None
        form = parse_form(raw_body)
        if form.get("event", "").startswith("ALIAS_"):
            return KIND_ALIAS, form, None
        if form.get("tr_id"):
            return KIND_TRANSACTION, form, None
        return KIND_UNKNOWN, form, None

    @staticmethod
    def _event_uid(kind: str, form: dict[str, str] | None, payload: dict | None) -> str:
        """Deterministyczny uid — tpay gwarantuje identyczny payload w ponowieniach."""
        if kind == KIND_ALIAS and form is not None:
            return f"alias:{form.get('event', '')}:{form.get('msg_value[value]', '')}"[:150]
        if kind == KIND_TOKENIZATION and payload is not None:
            data = payload.get("data") or {}
            return f"{payload.get('type', 'tokenization')}:{data.get('token', '')}"[:150]
        if form is not None:
            return f"{form.get('tr_id', '')}:{form.get('tr_status', '')}"[:150]
        return "unknown"

    # --- Handlery: aliasy BLIK (AC3) ---

    async def _handle_alias(
        self, form: dict[str, str], event_uid: str, existing: WebhookEvent | None
    ) -> tuple[bool, str]:
        event = form.get("event", "")
        alias_value = form.get("msg_value[value]", "")
        if not alias_value:
            # AC5: zwalidowany podpis, śmieciowy payload znanego typu → 400.
            await self._record_event(
                event_uid,
                form,
                WebhookProcessingStatus.REJECTED_PAYLOAD,
                type_=KIND_ALIAS,
                error_message="notyfikacja ALIAS_* bez msg_value[value]",
                row=existing,
            )
            logger.warning("tpay webhook %s: ALIAS_* bez wartości aliasu — odrzucony", event_uid)
            return False, WebhookProcessingStatus.REJECTED_PAYLOAD.value

        alias_type = form.get("msg_value[type]", "PAYID")
        expires_at = _parse_date(form.get("msg_value[expirationDate]"))
        status = _ALIAS_STATUS.get(event, TpayTokenStatus.ACTIVE)

        # Korelacja alias→tenant po transakcji rejestracji: checkout przekazuje
        # wygenerowaną przez nas wartość aliasu w blikPaymentData i zapisuje
        # ją w meta (docs tpay: wartość aliasu pochodzi od merchanta).
        txn = await self._find_alias_registration(alias_value)
        if txn is None:
            # AC3: brak dopasowania → warning (nie 500), audyt skipped, TRUE.
            logger.warning(
                "tpay webhook %s: brak transakcji rejestracji dla aliasu %r — pomijam",
                event_uid,
                alias_value,
            )
            await self._record_event(
                event_uid,
                form,
                WebhookProcessingStatus.SKIPPED,
                type_=KIND_ALIAS,
                error_message="alias bez dopasowania do tenanta",
                row=existing,
            )
            return True, WebhookProcessingStatus.SKIPPED.value

        service = SubscriptionService(self._db)
        if event == "ALIAS_REGISTER":
            kind = TokenKind.BLIK_ALIAS_UID if alias_type == "UID" else TokenKind.BLIK_ALIAS_PAYID
            await service.save_blik_alias_from_notification(
                txn.tenant_id, alias_value=alias_value, kind=kind, expires_at=expires_at
            )
        else:
            token = await service.update_blik_alias_status(
                txn.tenant_id, alias_value, tpay_status=status, expires_at=expires_at
            )
            if token is None:
                logger.warning(
                    "tpay webhook %s: alias %r bez lokalnego PaymentToken — pomijam",
                    event_uid,
                    alias_value,
                )
                await self._record_event(
                    event_uid,
                    form,
                    WebhookProcessingStatus.SKIPPED,
                    type_=KIND_ALIAS,
                    error_message="alias bez lokalnego PaymentToken",
                    row=existing,
                )
                return True, WebhookProcessingStatus.SKIPPED.value
            # AC3: wygaśnięcie/wyrejestrowanie przy aktywnej subskrypcji
            # cyklicznej → powiadomienie Ownera ("dodaj kartę lub ponów BLIK").
            if event in ("ALIAS_EXPIRED", "ALIAS_UNREGISTER"):
                await self._notify_owner_if_recurring(txn)

        await self._record_event(event_uid, form, WebhookProcessingStatus.PROCESSED, type_=KIND_ALIAS, row=existing)
        logger.info("tpay webhook %s: alias %s → %s", event_uid, alias_value, status.value)
        return True, WebhookProcessingStatus.PROCESSED.value

    async def _find_alias_registration(self, alias_value: str) -> PaymentTransaction | None:
        """Transakcja checkoutu, która zarejestrowała alias (meta.blik_alias_value)."""
        result = await self._db.execute(
            select(PaymentTransaction).where(PaymentTransaction.meta["blik_alias_value"].as_string() == alias_value)
        )
        return result.scalar_one_or_none()

    async def _notify_owner_if_recurring(self, registration_txn: PaymentTransaction) -> None:
        subscription = await SubscriptionService(self._db).get_current_subscription(registration_txn.tenant_id)
        if (
            subscription is None
            or subscription.status != SubscriptionStatus.ACTIVE
            or subscription.next_charge_at is None
            or subscription.cancel_at_period_end
        ):
            return
        owner_email = (registration_txn.meta or {}).get("payer_email")
        if owner_email:
            send_payment_method_expired_email_safely(owner_email, "alias BLIK")

    # --- Handlery: tokenizacja JSON (AC2, współpraca 7.2) ---

    async def _handle_tokenization(
        self, payload: dict, event_uid: str, existing: WebhookEvent | None
    ) -> tuple[bool, str]:
        data = payload.get("data") or {}
        token_value = data.get("token")
        if not token_value:
            await self._record_event(
                event_uid,
                payload,
                WebhookProcessingStatus.REJECTED_PAYLOAD,
                type_=KIND_TOKENIZATION,
                error_message="notyfikacja tokenizacyjna bez data.token",
                row=existing,
            )
            logger.warning("tpay webhook %s: JSON bez data.token — odrzucony", event_uid)
            return False, WebhookProcessingStatus.REJECTED_PAYLOAD.value

        # cliAuth (= nasz registration_id) koreluje notyfikację z rejestracją
        # POST /tokens (7.2 AC2); rekord PENDING niesie tenant_id.
        cli_auth = data.get("cliAuth") or data.get("tokenizationId") or payload.get("cliAuth")
        if cli_auth:
            result = await self._db.execute(select(PaymentToken).where(PaymentToken.registration_id == cli_auth))
            pending = result.scalar_one_or_none()
        else:
            pending = None

        if pending is None:
            # Bez korelacji nie wiemy, czyj token — warning + skipped (nie 500).
            logger.warning("tpay webhook %s: brak rejestracji dla cliAuth=%r — pomijam", event_uid, cli_auth)
            await self._record_event(
                event_uid,
                payload,
                WebhookProcessingStatus.SKIPPED,
                type_=KIND_TOKENIZATION,
                error_message="notyfikacja tokenizacyjna bez dopasowania rejestracji",
                row=existing,
            )
            return True, WebhookProcessingStatus.SKIPPED.value

        token = await SubscriptionService(self._db).save_card_token_from_notification(
            pending.tenant_id,
            token_value=str(token_value),
            registration_id=str(cli_auth) if cli_auth else None,
            card_tail=data.get("cardTail"),
            card_brand=data.get("cardBrand"),
        )
        token.expires_at = _parse_mmyy(data.get("tokenExpiryDate"))

        await self._record_event(
            event_uid, payload, WebhookProcessingStatus.PROCESSED, type_=KIND_TOKENIZATION, row=existing
        )
        logger.info("tpay webhook %s: token karty zapisany (rejestracja %s)", event_uid, cli_auth)
        return True, WebhookProcessingStatus.PROCESSED.value

    # --- Handler: transakcja (7.4, logika nietknięta) ---

    async def _handle_transaction(self, form: dict, event_uid: str, existing: WebhookEvent | None) -> tuple[bool, str]:
        # Korelacja wyłącznie po tr_crc == hidden_description (7.4 AC5).
        result = await self._db.execute(
            select(PaymentTransaction).where(PaymentTransaction.hidden_description == form.get("tr_crc"))
        )
        txn = result.scalar_one_or_none()
        if txn is None:
            await self._record_event(event_uid, form, WebhookProcessingStatus.NO_MATCH, row=existing)
            logger.error(
                "tpay webhook %s: brak lokalnego zamówienia dla tr_crc=%r — alert reconcile",
                event_uid,
                form.get("tr_crc"),
            )
            return True, WebhookProcessingStatus.NO_MATCH.value

        await self._record_event(event_uid, form, WebhookProcessingStatus.PROCESSED, row=existing)

        txn.title = form.get("tr_id")
        txn.test_mode = form.get("test_mode") == "1"
        paid, tr_amount = _decimals(form.get("tr_paid"), form.get("tr_amount"))
        is_recurring = (txn.meta or {}).get("source") == "recurring"
        # Sandbox tpay wysyła TRUE/FALSE wielkimi literami, a dokumentacja
        # klasycznego API pokazuje 'true' — porównania bezrolkowe (2026-09-14).
        tr_status = str(form.get("tr_status") or "").strip().lower()

        # Pełna kwota: tr_paid == tr_amount == kwota zamówienia (7.4 AC5).
        if tr_status == "true" and paid is not None and tr_amount is not None and paid == tr_amount == txn.amount:
            # Pełna kwota opłacona → status paid + aktywacja/odnowienie.
            txn.paid_amount = paid
            await self.mark_paid(txn)
            # 7.2 AC1: zapis karty przy pierwszej płatności (save=1) —
            # tpay dołącza card_token/card_tail/card_brand do notyfikacji.
            if form.get("card_token"):
                await SubscriptionService(self._db).save_card_token_from_webhook(
                    txn.tenant_id,
                    token_value=form["card_token"],
                    card_tail=form.get("card_tail"),
                    card_brand=form.get("card_brand"),
                )
        elif is_recurring and tr_status == "false":
            # 7.2 AC6: odnowienie ODRZUCONE (declined) → dunning (próba
            # ponowienia D+1/D+3/D+5), nie ręczna weryfikacja.
            txn.paid_amount = paid
            await self._handle_recurring_declined(txn, form, event_uid)
        else:
            # chargeback albo tr_paid != tr_amount → flaga do ręcznej weryfikacji,
            # bez automatycznej aktywacji (7.4 AC5/AC6; 7.2 Task 6.4 — na odnowieniu
            # dodatkowa flaga manual_review dla admina).
            txn.status = PaymentStatus.CHARGED_BACK
            if is_recurring:
                txn.meta = {**(txn.meta or {}), "manual_review": True}
            if paid is not None:
                txn.paid_amount = paid
            # 7.5 edge: nieudana płatność upgrade → rekord history canceled,
            # tenant zostaje na planie dotychczasowym (plan nie był zmieniany).
            if (txn.meta or {}).get("source") == "plan_change" and tr_status == "false":
                await SubscriptionService(self._db).cancel_failed_plan_change(txn)
            logger.error(
                "tpay webhook %s: transakcja %s wymaga ręcznej weryfikacji "
                "(tr_status=%r, tr_paid=%r, tr_amount=%r, oczekiwano %s)",
                event_uid,
                txn.hidden_description,
                form.get("tr_status"),
                form.get("tr_paid"),
                form.get("tr_amount"),
                txn.amount,
            )

        await self._db.flush()
        return True, WebhookProcessingStatus.PROCESSED.value

    async def mark_paid(self, txn: PaymentTransaction) -> None:
        """Status paid + aktywacja/odnowienie planu + email potwierdzenia.

        Wywoływane z webhooka (7.4 AC5) i z reconciliation fallbacku (7.4 AC7).
        Odnowienie (7.2, ``meta.source = recurring``): przedłużenie okresu
        przez ``renew_subscription`` zamiast aktywacji od zera (Task 5.4).
        """
        txn.status = PaymentStatus.PAID
        if txn.paid_amount is None:
            txn.paid_amount = txn.amount

        if txn.test_mode and not self._provider.settings.is_sandbox:
            # 7.4 AC5: notyfikacja z sandboxu nigdy nie aktywuje planu w produkcji.
            logger.critical(
                "BLOKADA: webhook test_mode=1 dla %s przy TPAY_ENV=production — bez aktywacji",
                txn.hidden_description,
            )
            return

        plan_raw = (txn.meta or {}).get("plan")
        try:
            plan_name = PlanName(plan_raw)
        except ValueError:
            logger.error("Webhook paid dla %s bez planu w meta (%r) — brak aktywacji", txn.hidden_description, plan_raw)
            return

        service = SubscriptionService(self._db)
        source = (txn.meta or {}).get("source")
        if source == "plan_change":
            # 7.5 AC1: upgrade prorated — finalizacja po `paid` (korelacja
            # hidden_description; plan zmieniany dopiero teraz).
            await service.finalize_plan_upgrade(txn)
        elif source == "recurring":
            await service.renew_subscription(txn.tenant_id, plan_name)
            logger.info("Odnowiono plan %s dla tenanta %s (order %s)", plan_name, txn.tenant_id, txn.hidden_description)
        else:
            await service.activate_paid_plan(txn.tenant_id, plan_name)
            logger.info(
                "Aktywowano plan %s dla tenanta %s (order %s)", plan_name, txn.tenant_id, txn.hidden_description
            )

        # 7.6 AC1: faktura VAT po każdej udanej płatności (zakup, odnowienie,
        # upgrade — jedna ścieżka po `paid`; także z reconciliation 7.4 AC7,
        # idempotentna po payment_id). Best-effort: porażka nie wywala
        # webhooka (5xx → zbędne ponowienia całej płatności).
        await self._generate_invoice_safely(txn)

        payer_email = (txn.meta or {}).get("payer_email")
        if payer_email:
            _send_confirmation_email_safely(payer_email, plan_raw, txn)

    async def _generate_invoice_safely(self, txn: PaymentTransaction) -> None:
        """7.6 AC1 — rekord Invoice + enqueue Celery (PDF/email, AC2/AC3).

        Metoda płatności: ``card_token`` w notyfikacji → karta (7.2 AC1);
        w pozostałych przypadkach karta jako domyślna — notyfikacja
        transakcyjna tpay nie niesie grupy/kanału płatności (ograniczenie
        u źródła, patrz Dev Agent Record story 7.6).
        """
        from app.models.invoice import InvoicePaymentMethod
        from app.workers.tasks.generate_invoice_pdf import generate_invoice_pdf

        method = InvoicePaymentMethod.CARD
        try:
            # Savepoint: porażka faktury (błąd SQL, brak snapshotu) nie może
            # zatruć transakcji webhooka — w PostgreSQL po nieudanym
            # statement cała transakcja jest aborted i commit aktywacji
            # planu by padł (wykryte na sandboxie 2026-09-14: mail
            # potwierdzenia wyszedł, a całość się wycofała).
            async with self._db.begin_nested():
                invoice = await InvoiceService(self._db).generate_invoice(txn.tenant_id, txn, payment_method=method)
            generate_invoice_pdf.delay(str(invoice.id))
        except Exception:
            logger.exception(
                "Faktura dla order %s nie wygenerowana — wymagany replay webhooka",
                txn.hidden_description,
            )

    async def _handle_recurring_declined(self, txn: PaymentTransaction, form: dict, event_uid: str) -> None:
        """7.2 AC6 — odnowienie odrzucone: wejście w dunning (D+1/D+3/D+5)."""
        service = SubscriptionService(self._db)
        subscription = await service.get_current_subscription(txn.tenant_id)
        if subscription is None:
            logger.error(
                "tpay webhook %s: odnowienie %s odrzucone bez subskrypcji — alert",
                event_uid,
                txn.hidden_description,
            )
            return
        owner_email = (txn.meta or {}).get("payer_email")
        await service.register_failed_charge(subscription, owner_email=owner_email)
        logger.warning(
            "tpay webhook %s: odnowienie %s odrzucone — dunning (próba %s)",
            event_uid,
            txn.hidden_description,
            subscription.dunning_attempt,
        )

    # --- Audyt (AC4) ---

    async def _fetch_event(self, event_uid: str) -> WebhookEvent | None:
        result = await self._db.execute(select(WebhookEvent).where(WebhookEvent.event_uid == event_uid))
        return result.scalar_one_or_none()

    async def _record_event(
        self,
        event_uid: str,
        raw: dict,
        status: WebhookProcessingStatus,
        *,
        type_: str = KIND_TRANSACTION,
        error_message: str | None = None,
        row: WebhookEvent | None | _Unset = _UNSET,
    ) -> None:
        """Audyt każdego żądania (AC4) — upsert po event_uid (ponowienia tpay
        po odrzuceniu aktualizują ten sam wiersz, nie dublują go).
        ``row`` — wiersz z wcześniejszego odczytu (deduplikacja); ``None``
        oznacza „odczytano, nie było" (bez ponownego zapytania)."""
        if isinstance(row, _Unset):
            row = await self._fetch_event(event_uid)
        if row is not None:
            row.raw = raw
            row.processing_status = status
            row.error_message = error_message
            if status == WebhookProcessingStatus.PROCESSED:
                row.processed_at = datetime.now(UTC)
        else:
            self._db.add(
                WebhookEvent(
                    event_uid=event_uid,
                    provider="tpay",
                    type=type_,
                    raw=raw,
                    processing_status=status,
                    error_message=error_message,
                    processed_at=datetime.now(UTC) if status == WebhookProcessingStatus.PROCESSED else None,
                )
            )
        await self._db.flush()


def _decimals(*values: str | None) -> tuple[Decimal | None, ...]:
    out: list[Decimal | None] = []
    for value in values:
        try:
            out.append(Decimal(str(value)) if value is not None else None)
        except InvalidOperation:
            out.append(None)
    return tuple(out)


def _parse_date(value: str | None) -> datetime | None:
    """Data z notyfikacji aliasu (``msg_value[expirationDate]``, YYYY-MM-DD)."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).replace(tzinfo=UTC)
    except ValueError:
        logger.warning("tpay webhook: nieparsowalna data wygaśnięcia aliasu %r", value)
        return None


def _parse_mmyy(value: str | None) -> datetime | None:
    """``tokenExpiryDate`` (MMYY) → koniec miesiąca ważności karty."""
    if not value or len(str(value)) != 4 or not str(value).isdigit():
        return None
    month, year = int(str(value)[:2]), 2000 + int(str(value)[2:])
    if not 1 <= month <= 12:
        return None
    end_of_month = datetime(year, month, 1, tzinfo=UTC) + timedelta(days=32)
    return end_of_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)


def _send_confirmation_email_safely(email: str, plan: str, txn: PaymentTransaction) -> None:
    """Email potwierdzenia płatności (7.4 AC5) — best-effort, nie wywala webhooka."""
    from app.services.email.email_service import send_payment_confirmation_email

    try:
        send_payment_confirmation_email(
            email=email,
            plan_display=plan.capitalize(),
            amount=f"{txn.paid_amount} {txn.currency}",
            period_end=txn.meta.get("period_end_hint", ""),
        )
    except Exception:
        logger.warning("Email potwierdzenia dla %s nie wysłany — webhook kontynuuje", email, exc_info=True)
