"""Dane testowe sandbox tpay + helpery notyfikacji — Story 7.4 (§2.1, §3.2a).

Kwoty sterujące scenariuszami tpay są STAŁYMI pomocniczymi — NIE cenami
planów (ceny planów z env: ``BILLING_*_MONTHLY_PRICE``, §3.2a).
Karty/BLIK/PAYID/3DS wg dokumentacji sandbox (docs-api.tpay.com).

Helpery: poprawny ``md5sum``, body notyfikacji form-urlencoded oraz JWS
podpisany generowanym certyfikatem testowym (przypinanym w testach zamiast
pobierania PEM z secure.tpay.com).
"""

import base64
import hashlib
import json
import random
from datetime import UTC, datetime
from functools import lru_cache
from urllib.parse import quote_plus, urlencode

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

# --- Dane sandbox (§2.1) — do testów integracyjnych marker `billing` ---

TPAY_TEST_CARDS = [
    "2223000280000016",
    "4056217843597258",
    "5204740000001002",
    "5457210002001016",
]
# 3DS wg groszy kwoty: x1 frictionless, x3 sukces, x5 błąd 3DS, x6 decline.
TPAY_3DS_SUFFIXES = {"frictionless": "x1", "success": "x3", "error_3ds": "x5", "decline": "x6"}
# Kwoty wymuszające błędy (karta/wallety; 504.00 dodatkowo dla samego tokena).
TPAY_CARD_ERROR_AMOUNTS = ["500.00", "501.00", "503.00", "504.00"]
# BLIK: poprawny kod 777xxx; kwoty błędów BLIK.
TPAY_BLIK_CODE_PREFIX = "777"
TPAY_BLIK_ERROR_AMOUNTS = {
    "rejected_by_payer": "144.00",
    "rejected_by_issuer": "168.00",
    "insufficient_funds": "120.00",
    "timeout": "312.00",
    "limit_exceeded": "96.00",
    "security": "216.00",
}
# Rejestracja aliasu PAYID (Płatności Powtarzalne).
TPAY_PAYID_CODES = [f"9990{n:02d}" for n in range(9, 17)]  # 999009-999016
# Aliasy PAYID żyją ≥ tydzień na kwotach z groszami x.08-x.15 (§2.1) —
# testy recurring wyłącznie w tym zakresie (kody 999xxx są czyszczone co 15 min).
TPAY_PAYID_AMOUNT_SUFFIXES = tuple(f"{n:02d}" for n in range(8, 16))  # "08"-"15"
# Scenariusz: bank nie obsługuje Płatności Powtarzalnych.
TPAY_BANK_NO_REPEATABLE_AMOUNT = "495.00"
# Scenariusz: ekran challenge 3DS — dowolne grosze poza x1/x3/x5/x6.
TPAY_3DS_CHALLENGE_AMOUNTS = ("30.02", "30.77")
# Dane karty na Panelu Transakcyjnym sandbox (CVC = 3 losowe cyfry, przyszła data).
TPAY_TEST_CVV = "123"
TPAY_TEST_CARD_EXPIRY = ("12", "2030")


def blik_code() -> str:
    """Poprawny kod BLIK sandbox: ``777`` + 3 dowolne cyfry (§2.1)."""
    return f"777{random.randint(0, 999):03d}"


def payid_amount(whole: str = "30") -> str:
    """Kwota w zakresie rejestracji aliasu PAYID (``x.08`` z x.08-x.15)."""
    return f"{whole}.{TPAY_PAYID_AMOUNT_SUFFIXES[0]}"


# --- Wartości konfiguracyjne testów jednostkowych (sekrety tylko testowe) ---

TEST_MERCHANT_ID = "1010-test"
TEST_SECURITY_CODE = "test-security-code"
TEST_CLIENT_ID = "test-client-id"
TEST_CLIENT_SECRET = "test-client-secret"

# Kwota testowa dla scenariusza create-transaction w sandboxie (nie cena planu!).
TPAY_SANDBOX_CHECKOUT_AMOUNT = "30.00"


def compute_md5sum(merchant_id: str, tr_id: str, tr_amount: str, tr_crc: str, security_code: str) -> str:
    """Wzór tpay: md5(id + tr_id + tr_amount + tr_crc + kod_zabezpieczający)."""
    concat = f"{merchant_id}{tr_id}{tr_amount}{tr_crc}{security_code}"
    return hashlib.md5(concat.encode("utf-8")).hexdigest()


def build_notification(
    *,
    tr_id: str = "TR-123456",
    tr_crc: str = "ord-1",
    tr_amount: str = "30.00",
    tr_paid: str | None = "30.00",
    tr_status: str = "true",
    test_mode: str = "1",
    card_token: str | None = None,
    merchant_id: str = TEST_MERCHANT_ID,
    security_code: str = TEST_SECURITY_CODE,
    md5sum_override: str | None = None,
) -> bytes:
    """Surowe body notyfikacji (form-urlencoded) z poprawnym md5sum."""
    fields: dict[str, str] = {
        "tr_id": tr_id,
        "tr_crc": tr_crc,
        "tr_amount": tr_amount,
        "tr_paid": tr_paid if tr_paid is not None else tr_amount,
        "tr_status": tr_status,
        "test_mode": test_mode,
        "md5sum": md5sum_override or compute_md5sum(merchant_id, tr_id, tr_amount, tr_crc, security_code),
    }
    if card_token:
        fields.update({"card_token": card_token, "card_tail": "0016", "card_brand": "mastercard"})
    return urlencode(fields, quote_via=quote_plus).encode("utf-8")


# --- Story 7.3: notyfikacje aliasów BLIK + tokenizacyjne JSON (§3.4, docs-api.tpay.com) ---


def build_alias_notification(
    *,
    event: str = "ALIAS_REGISTER",
    alias_value: str = "tg-alias-123",
    alias_type: str = "PAYID",  # PAYID (Płatności Powtarzalne) | UID (One Click)
    expiration: str | None = "2028-09-03",
    merchant_id: str = TEST_MERCHANT_ID,
) -> bytes:
    """Form-urlencoded notyfikacja aliasu BLIK (AC2/AC3).

    Struktura wg docs tpay: ``id``, ``event`` (ALIAS_REGISTER|ALIAS_UNREGISTER|
    ALIAS_UPDATE|ALIAS_EXPIRED), ``msg_value[value]``, ``msg_value[type]``,
    ``msg_value[expirationDate]`` (brak = alias bezterminowy), ``md5sum``
    (deprecated — JWS jest gwarancją pochodzenia).
    """
    fields: dict[str, str] = {"id": merchant_id, "event": event, "msg_value[value]": alias_value}
    if alias_type:
        fields["msg_value[type]"] = alias_type
    if expiration is not None:
        fields["msg_value[expirationDate]"] = expiration
    return urlencode(fields, quote_via=quote_plus).encode("utf-8")


def build_tokenization_notification(
    *,
    token: str = "fdc235a1b2c3d4e5" * 4,  # 64 znaki jak u tpay
    notification_type: str = "tokenization",
    cli_auth: str | None = "reg-cli-auth-1",
    card_tail: str = "1111",
    card_brand: str = "Mastercard",
    token_expiry: str = "0628",  # MMYY
) -> bytes:
    """JSON notyfikacja tokenizacyjna (AC2): ``data.token`` po rejestracji
    ``POST /tokens``. ``cliAuth`` (nasz registration_id) wraca w ``data.cliAuth``."""
    data: dict = {
        "token": token,
        "cardTail": card_tail,
        "cardBrand": card_brand,
        "tokenExpiryDate": token_expiry,
    }
    if cli_auth:
        data["cliAuth"] = cli_auth
    return json.dumps({"type": notification_type, "data": data}).encode("utf-8")


# --- JWS: generowany certyfikat podpisujący (zamiast PEM z secure.tpay.com) ---


@lru_cache
def _signing_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@lru_cache
def signing_cert_pem() -> str:
    """Certyfikat testowy (PEM) — przypinany w ``TpayWebhookVerifier``."""
    key = _signing_key()
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "tpay-test-notifications")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime(2020, 1, 1, tzinfo=UTC))
        .not_valid_after(datetime(2040, 1, 1, tzinfo=UTC))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM).decode("ascii")


@lru_cache
def signing_cert_der_b64() -> str:
    """Ten sam certyfikat w DER base64 — pola ``x5c`` nagłówka JWS."""
    cert = x509.load_pem_x509_certificate(signing_cert_pem().encode())
    return base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode("ascii")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def sign_jws(raw_body: bytes, *, alg: str = "RS256") -> str:
    """Kompaktowy JWS nad ``raw_body`` kluczem testowym (RS256)."""
    key = _signing_key()
    header = {"alg": alg, "x5c": [signing_cert_der_b64()]}
    header_b64 = _b64url(json.dumps(header).encode())
    payload_b64 = _b64url(raw_body)
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    if alg == "RS256":
        from cryptography.hazmat.primitives.asymmetric import padding as _pad

        signature = key.sign(signing_input, _pad.PKCS1v15(), hashes.SHA256())
    else:
        raise ValueError(f"unsupported test alg: {alg}")
    return f"{header_b64}.{payload_b64}.{_b64url(signature)}"


def sign_jws_detached(
    raw_body: bytes,
    *,
    alg: str = "RS256",
    include_x5c: bool = True,
    x5u: str | None = None,
    signing_key: rsa.RSAPrivateKey | None = None,
) -> str:
    """Detached JWS (RFC 7515 §3.1) — format realnych notyfikacji tpay:
    środkowy segment (payload) PUSTY, podpis liczony nad ``base64url(raw_body)``
    (wzór: oficjalny przykład PHP z docs webhooks tpay).

    ``include_x5c=False`` + ``x5u`` — wariant bez ``x5c`` w nagłówku
    (certyfikat podpisujący pod URL-em), obserwowany na sandboxie.
    ``signing_key`` — domyślnie klucz główny (pinned); testy x5u podpisują
    kluczem sandboxowym (``_sandbox_signing_key``).
    """
    key = signing_key or _signing_key()
    header: dict = {"alg": alg}
    if include_x5c:
        header["x5c"] = [signing_cert_der_b64()]
    if x5u:
        header["x5u"] = x5u
    header_b64 = _b64url(json.dumps(header).encode())
    payload_b64 = _b64url(raw_body)
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    if alg == "RS256":
        from cryptography.hazmat.primitives.asymmetric import padding as _pad

        signature = key.sign(signing_input, _pad.PKCS1v15(), hashes.SHA256())
    else:
        raise ValueError(f"unsupported test alg: {alg}")
    return f"{header_b64}..{_b64url(signature)}"


@lru_cache
def _sandbox_signing_key() -> rsa.RSAPrivateKey:
    """Klucz „sandboxowy" — inny niż główny (pinned produkcyjny); symuluje
    sytuację, gdy środowisko sandbox tpay podpisuje inną parą kluczy, a
    certyfikat podaje tylko przez ``x5u``."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@lru_cache
def sandbox_signing_cert_pem() -> str:
    key = _sandbox_signing_key()
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "tpay-sandbox-notifications")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime(2020, 1, 1, tzinfo=UTC))
        .not_valid_after(datetime(2040, 1, 1, tzinfo=UTC))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM).decode("ascii")


@lru_cache
def _foreign_key() -> rsa.RSAPrivateKey:
    """Drugi, obcy klucz — podpis „z innego klucza" (7.3 AC1)."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@lru_cache
def foreign_signing_cert_pem() -> str:
    """Certyfikat obcego klucza (PEM) — prawidłowy x509, nie przypięty."""
    key = _foreign_key()
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "foreign-signer")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime(2020, 1, 1, tzinfo=UTC))
        .not_valid_after(datetime(2040, 1, 1, tzinfo=UTC))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM).decode("ascii")


def sign_jws_with_foreign_key(raw_body: bytes) -> str:
    """JWS podpisany OBCYM kluczem z własnym (obcym) certyfikatem w x5c —
    poprawna struktura, podpis zgodny z x5c, ale klucz ≠ przypięty."""
    from cryptography.hazmat.primitives.asymmetric import padding as _pad

    key = _foreign_key()
    cert = x509.load_pem_x509_certificate(foreign_signing_cert_pem().encode())
    der_b64 = base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode("ascii")
    header_b64 = _b64url(json.dumps({"alg": "RS256", "x5c": [der_b64]}).encode())
    payload_b64 = _b64url(raw_body)
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = key.sign(signing_input, _pad.PKCS1v15(), hashes.SHA256())
    return f"{header_b64}.{payload_b64}.{_b64url(signature)}"


def make_test_billing_settings(**overrides):
    """BillingSettings z sekretnymi wartościami TESTOWYMI (sandbox)."""
    from pydantic import SecretStr

    from app.core.config_billing import BillingSettings

    defaults = dict(
        tpay_env="sandbox",
        tpay_client_id=TEST_CLIENT_ID,
        tpay_client_secret=SecretStr(TEST_CLIENT_SECRET),
        tpay_security_code=SecretStr(TEST_SECURITY_CODE),
        tpay_merchant_id=TEST_MERCHANT_ID,
    )
    defaults.update(overrides)
    return BillingSettings(**defaults)
