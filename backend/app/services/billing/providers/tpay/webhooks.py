"""Weryfikacja notyfikacji tpay — JWS + md5sum (Story 7.4, AC3).

tpay nie udostępnia whitelisty IP — weryfikacja JWS jest obowiązkowa
(podpis w nagłówku ``X-JWS-Signature``, certyfikaty x509 tpay + root CA),
a ``md5sum`` działa jako druga warstwa:

    md5sum == md5(TPAY_MERCHANT_ID + tr_id + tr_amount + tr_crc + TPAY_SECURITY_CODE)

Weryfikacja JWS idzie po prymitywach ``cryptography`` (już w deps — ten
sam stack co RS256 dla JWT aplikacji); celowo BEZ python-jose (nieutrzymywana,
znane CVE). tpay wysyła **detached JWS** (RFC 7515 §3.1 — pusty środkowy
segment, podpis nad ``base64url(surowego body)``); wariant z osadzonym
payloadem jest też akceptowany, o ile jest tożsamy z body (anti-swap).
"""

import base64
import hashlib
import hmac
import json
import logging
import time
from urllib.parse import parse_qs, urlparse

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from app.core.config_billing import BillingSettings

logger = logging.getLogger(__name__)

JWS_HEADER_NAME = "X-JWS-Signature"
_ALLOWED_ALGS = {"RS256": hashes.SHA256, "RS512": hashes.SHA512}

# Cache pobranych certyfikatów (7.4 AC3/Task 5.2 + 7.3 Task 2.1 — rotacja):
# {url: (pem, fetched_at_monotonic)}. ``_PREV_CERT_CACHE`` trzyma certyfikat
# sprzed ostatniego odświeżenia — tpay podpisuje równolegle oboma krótko po
# rotacji, więc notyfikacje „w locie" ze starego klucza pozostają akceptowane.
_CERT_CACHE: dict[str, tuple[str, float]] = {}
_PREV_CERT_CACHE: dict[str, str] = {}
_CERT_CACHE_TTL = 24 * 3600


def _b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


async def _fetch_cert_pem(url: str) -> str:
    """Pobranie PEM z URL tpay (wyalokowane pod mocki w testach)."""
    async with httpx.AsyncClient(timeout=15.0) as http:
        resp = await http.get(url)
        resp.raise_for_status()
        return resp.text


async def _cert_pem_from_x5u(x5u: str) -> str | None:
    """PEM spod nagłówka JWS ``x5u`` — wyłącznie domeny tpay (anti-SSRF;
    zaufanie = TLS + allowlista, jak dla ``TPAY_JWS_CERT_URL``). None = brak."""
    try:
        host = urlparse(x5u).hostname or ""
    except ValueError:
        return None
    if host != "tpay.com" and not host.endswith(".tpay.com"):
        logger.warning("tpay JWS: x5u spoza domeny tpay (%r) — ignoruję", x5u)
        return None
    return await _fetch_cert_pem(x5u)


def _safe_jws_header(jws_compact: str) -> str:
    """Zdekodowany nagłówek JWS do logów diagnostycznych (alg/x5c/x5u/kid —
    brak sekretów), obcięty do 300 znaków."""
    try:
        return str(json.loads(_b64url_decode(jws_compact.split(".")[0])))[:300]
    except Exception:
        return "?"


async def get_pinned_cert_pem(settings: BillingSettings, *, force_refresh: bool = False) -> str:
    """Certyfikat do przypięcia (PEM) — z cache albo pobrany z ``TPAY_JWS_CERT_URL``.

    ``force_refresh=True`` (rotacja — x5c nie pasuje do przypiętego): pobranie
    z pominięciem TTL; poprzedni PEM trafia do ``_PREV_CERT_CACHE`` (grace).
    """
    url = settings.tpay_jws_cert_url
    now = time.monotonic()
    cached = _CERT_CACHE.get(url)
    if not force_refresh and cached and now - cached[1] < _CERT_CACHE_TTL:
        return cached[0]

    pem = await _fetch_cert_pem(url)
    if cached and cached[0] != pem:
        _PREV_CERT_CACHE[url] = cached[0]
    _CERT_CACHE[url] = (pem, now)
    return pem


class TpayWebhookVerifier:
    """Weryfikacja podpisu notyfikacji transakcyjnej (AC3)."""

    def __init__(self, settings: BillingSettings, pinned_cert_pem: str | None = None) -> None:
        self._settings = settings
        self._pinned_cert_pem = pinned_cert_pem  # None → pobierz z URL (cache)

    async def verify(self, raw_body: bytes, jws_signature: str | None) -> bool:
        """JWS (jeśli konfiguracja przewiduje certyfikat) + md5sum — obie warstwy."""
        if not jws_signature:
            return False
        if not await self.verify_jws(jws_signature, raw_body):
            return False
        return self.verify_md5sum(raw_body)

    def verify_md5sum(self, raw_body: bytes) -> bool:
        """Druga warstwa: md5(merchant_id + tr_id + tr_amount + tr_crc + security_code)."""
        form = {k: v[0] for k, v in parse_qs(raw_body.decode("utf-8", errors="replace")).items()}
        required = ("tr_id", "tr_amount", "tr_crc", "md5sum")
        if any(not form.get(field) for field in required):
            return False
        expected = self.compute_md5sum(tr_id=form["tr_id"], tr_amount=form["tr_amount"], tr_crc=form["tr_crc"])
        return hmac.compare_digest(expected, form["md5sum"])

    def compute_md5sum(self, *, tr_id: str, tr_amount: str, tr_crc: str) -> str:
        secret = self._settings.tpay_security_code.get_secret_value()
        concat = f"{self._settings.tpay_merchant_id}{tr_id}{tr_amount}{tr_crc}{secret}"
        return hashlib.md5(concat.encode("utf-8")).hexdigest()

    async def verify_jws(self, jws_compact: str, raw_body: bytes) -> bool:
        """Pierwsza warstwa: podpis RS256/RS512 certyfikatem tpay (przypiętym).

        Rotacja certyfikatów tpay (7.3 Task 2.1): gdy ``x5c`` nie pasuje do
        przypiętego certyfikatu, dokładnie jedno wymuszone odświeżenie cache
        (bypass TTL) — nowa para kluczy jest akceptowana od razu; krótko po
        rotacji akceptowany jest też certyfikat poprzedni (prev-cache, grace
        dla notyfikacji podpisanych w locie starym kluczem).
        """
        try:
            header_b64, payload_b64, signature_b64 = jws_compact.split(".")
            header = json.loads(_b64url_decode(header_b64))
            alg = header["alg"]
            if alg not in _ALLOWED_ALGS:
                logger.warning("tpay JWS: nieobsługiwany alg %r", alg)
                return False

            # Detached JWS (RFC 7515 §3.1) — format realnych notyfikacji tpay:
            # środkowy segment jest PUSTY, podpis liczony nad base64url(surowego
            # body). Gdy payload jest osadzony, musi być tożsamy z body
            # (anti-swap) — wtedy base64url(body) daje identyczny segment i
            # jedna ścieżka weryfikacji obsługuje oba warianty.
            computed_payload_b64 = base64.urlsafe_b64encode(raw_body).rstrip(b"=").decode("ascii")
            if payload_b64 and payload_b64 != computed_payload_b64:
                logger.warning("tpay JWS: osadzony payload nie zgadza się z body żądania")
                return False

            x5c = header.get("x5c")
            x5u = header.get("x5u")
            pinned_pem = self._pinned_cert_pem or await get_pinned_cert_pem(self._settings)
            pinned_cert = x509.load_pem_x509_certificate(pinned_pem.encode())

            if x5c:
                # Podstawowa ścieżka: certyfikat osadzony w nagłówku + pinning.
                leaf_cert = x509.load_der_x509_certificate(base64.b64decode(x5c[0]))
                leaf_numbers = leaf_cert.public_key().public_numbers()

                # Przypięcie: certyfikat z x5c musi być tym samym kluczem co pinned.
                if leaf_numbers != pinned_cert.public_key().public_numbers():
                    # Rotacja? Jedno wymuszone odświeżenie i porównanie ponownie.
                    refreshed_pem = await get_pinned_cert_pem(self._settings, force_refresh=True)
                    refreshed_cert = x509.load_pem_x509_certificate(refreshed_pem.encode())
                    if leaf_numbers == refreshed_cert.public_key().public_numbers():
                        pinned_cert = refreshed_cert
                        logger.info("tpay JWS: zaakceptowano certyfikat po rotacji (odświeżono cache)")
                    else:
                        # Grace: poprzedni certyfikat (notyfikacje w locie po rotacji).
                        prev_pem = _PREV_CERT_CACHE.get(self._settings.tpay_jws_cert_url)
                        if (
                            prev_pem
                            and leaf_numbers
                            == x509.load_pem_x509_certificate(prev_pem.encode()).public_key().public_numbers()
                        ):
                            pinned_cert = x509.load_pem_x509_certificate(prev_pem.encode())
                            logger.info("tpay JWS: zaakceptowano certyfikat poprzedni (grace po rotacji)")
                        else:
                            logger.warning("tpay JWS: certyfikat x5c nie pasuje do przypiętego certyfikatu")
                            return False
            elif x5u:
                # Sandbox tpay: certyfikat podpisujący tylko pod URL-em (``x5u``),
                # klucz ≠ przypięty PEM — pobranie z allowlisty domen tpay.
                x5u_pem = await _cert_pem_from_x5u(x5u)
                if not x5u_pem:
                    return False
                leaf_cert = x509.load_pem_x509_certificate(x5u_pem.encode())
                logger.info("tpay JWS: weryfikacja certyfikatem z x5u (%s)", x5u)
            else:
                # Bez x5c/x5u — weryfikacja wprost kluczem przypiętego
                # certyfikatu: podpis musi pasować do pinned, więc gwarancja
                # pochodzenia zachowana.
                leaf_cert = pinned_cert

            signing_input = f"{header_b64}.{computed_payload_b64}".encode("ascii")
            signature = _b64url_decode(signature_b64)
            leaf_cert.public_key().verify(
                signature,
                signing_input,
                padding.PKCS1v15(),
                _ALLOWED_ALGS[alg](),
            )
            return True
        except Exception:
            logger.warning(
                "tpay JWS: weryfikacja nie powiodła się (header=%s, body_len=%d, body_sha256=%s)",
                _safe_jws_header(jws_compact),
                len(raw_body),
                hashlib.sha256(raw_body).hexdigest()[:16],
                exc_info=True,
            )
            return False
