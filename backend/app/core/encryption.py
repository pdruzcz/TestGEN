"""Fernet symmetric encryption for sensitive data at rest (e.g., TOTP secrets).

Story 1.54 adds per-tenant AES-256-GCM helpers for the anonymization mapping:
each tenant's mapping is encrypted under a key derived (HKDF-SHA256) from the
master ``encryption_key`` and the tenant UUID, so mappings from one tenant
cannot be decrypted with another tenant's context (defence in depth on top of
RLS).
"""

import base64
import os
import uuid

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import get_settings

_HKDF_INFO = b"testgen/anonymization-mapping/v1"
_NONCE_BYTES = 12  # AESGCM recommended nonce size


def _get_fernet() -> Fernet:
    settings = get_settings()
    return Fernet(settings.encryption_key.encode())


def encrypt(plaintext: str) -> str:
    """Encrypt a string and return the Fernet token as a UTF-8 string."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a Fernet token back to the original string."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()


def derive_tenant_key(tenant_id: uuid.UUID) -> bytes:
    """Derive a 32-byte AES-256 key for a tenant (HKDF-SHA256 over master key)."""
    master = base64.urlsafe_b64decode(get_settings().encryption_key.encode())
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=tenant_id.bytes,
        info=_HKDF_INFO,
    ).derive(master)


def encrypt_bytes_for_tenant(data: bytes, tenant_id: uuid.UUID) -> bytes:
    """AES-256-GCM encrypt bytes under the tenant key. Returns nonce||ciphertext."""
    key = derive_tenant_key(tenant_id)
    nonce = os.urandom(_NONCE_BYTES)
    return nonce + AESGCM(key).encrypt(nonce, data, None)


def decrypt_bytes_for_tenant(blob: bytes, tenant_id: uuid.UUID) -> bytes:
    """Decrypt nonce||ciphertext produced by :func:`encrypt_bytes_for_tenant`."""
    key = derive_tenant_key(tenant_id)
    nonce, ciphertext = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
    return AESGCM(key).decrypt(nonce, ciphertext, None)


# ── Epic 8: tokeny OAuth integracji SCM (Story 8.1) ─────────────────────────


def encrypt_token(plaintext: str, tenant_id: uuid.UUID) -> str:
    """AES-256-GCM szyfrowanie tokenu pod kluczem tenanta; zwraca base64.

    Token OAuth do GitHuba/GitLaba daje dostęp do cudzego kodu, więc — jak
    mapowanie anonimizacji (1.54) — jest szyfrowany kluczem wyprowadzonym
    z tenanta, a nie kluczem globalnym: wyciek bazy bez kontekstu tenanta
    nie wystarcza do odszyfrowania.
    """
    blob = encrypt_bytes_for_tenant(plaintext.encode("utf-8"), tenant_id)
    return base64.urlsafe_b64encode(blob).decode("ascii")


def decrypt_token(ciphertext: str, tenant_id: uuid.UUID) -> str:
    """Odwrotność :func:`encrypt_token`. Rzuca, gdy tenant lub szyfrogram się nie zgadza."""
    blob = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
    return decrypt_bytes_for_tenant(blob, tenant_id).decode("utf-8")
