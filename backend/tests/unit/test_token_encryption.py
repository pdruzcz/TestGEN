"""Testy szyfrowania tokenów integracji — Story 8.1 (AC1; Task 7.2).

``encrypt_token``/``decrypt_token`` to AES-256-GCM pod kluczem wyprowadzonym
z tenanta (HKDF nad master key) — te testy pilnują obu własności: odwracalności
i izolacji między tenantami.
"""

import base64
import uuid

import pytest
from cryptography.exceptions import InvalidTag

from app.core.encryption import decrypt_token, encrypt_token

TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")


def test_roundtrip_zwraca_oryginal():
    token = "gho_" + "x" * 36
    assert decrypt_token(encrypt_token(token, TENANT_A), TENANT_A) == token


def test_szyfrogram_nie_zawiera_jawnego_tokenu():
    token = "gho_sekretnawartosc"
    assert token not in encrypt_token(token, TENANT_A)


def test_ten_sam_token_szyfruje_sie_za_kazdym_razem_inaczej():
    """Losowy nonce — powtarzalny szyfrogram zdradzałby, że token się nie zmienił."""
    token = "gho_abc"
    assert encrypt_token(token, TENANT_A) != encrypt_token(token, TENANT_A)


def test_token_innego_tenanta_nie_da_sie_odszyfrowac():
    cipher = encrypt_token("gho_abc", TENANT_A)
    with pytest.raises(InvalidTag):
        decrypt_token(cipher, TENANT_B)


def test_zmodyfikowany_szyfrogram_jest_odrzucany():
    """GCM wykrywa manipulację — bez tego dałoby się podmienić token w bazie."""
    cipher = encrypt_token("gho_abc", TENANT_A)
    blob = bytearray(base64.urlsafe_b64decode(cipher))
    blob[-1] ^= 0x01
    tampered = base64.urlsafe_b64encode(bytes(blob)).decode()

    with pytest.raises(InvalidTag):
        decrypt_token(tampered, TENANT_A)


def test_smieciowy_szyfrogram_rzuca():
    with pytest.raises(Exception):  # noqa: B017 — dowolny błąd, byle nie cichy przelot
        decrypt_token("to-nie-jest-szyfrogram", TENANT_A)


def test_obsluguje_puste_i_dlugie_wartosci():
    assert decrypt_token(encrypt_token("", TENANT_A), TENANT_A) == ""
    long_token = "t" * 5000
    assert decrypt_token(encrypt_token(long_token, TENANT_A), TENANT_A) == long_token


def test_obsluguje_znaki_spoza_ascii():
    value = "token-zażółć-gęślą-jaźń"
    assert decrypt_token(encrypt_token(value, TENANT_A), TENANT_A) == value
