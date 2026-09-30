"""Tests for per-tenant AES-256-GCM mapping encryption — Story 1.54."""

import uuid

import pytest
from cryptography.exceptions import InvalidTag

from app.core.encryption import (
    decrypt_bytes_for_tenant,
    derive_tenant_key,
    encrypt_bytes_for_tenant,
)


class TestDeriveTenantKey:
    def test_key_is_32_bytes(self):
        # AES-256 requires a 256-bit (32-byte) key.
        key = derive_tenant_key(uuid.uuid4())
        assert len(key) == 32

    def test_keys_differ_per_tenant(self):
        assert derive_tenant_key(uuid.uuid4()) != derive_tenant_key(uuid.uuid4())

    def test_key_deterministic_per_tenant(self):
        tid = uuid.uuid4()
        assert derive_tenant_key(tid) == derive_tenant_key(tid)


class TestTenantBytesRoundtrip:
    def test_roundtrip(self):
        tid = uuid.uuid4()
        blob = encrypt_bytes_for_tenant(b'{"<IDENT_001>": "PaymentGateway"}', tid)
        assert isinstance(blob, bytes)
        assert decrypt_bytes_for_tenant(blob, tid) == b'{"<IDENT_001>": "PaymentGateway"}'

    def test_ciphertext_differs_from_plaintext(self):
        tid = uuid.uuid4()
        blob = encrypt_bytes_for_tenant(b"secret-value", tid)
        assert b"secret-value" not in blob

    def test_random_nonce_per_encryption(self):
        tid = uuid.uuid4()
        # Same plaintext twice → different ciphertexts (random nonce).
        assert encrypt_bytes_for_tenant(b"x", tid) != encrypt_bytes_for_tenant(b"x", tid)

    def test_cross_tenant_decrypt_fails(self):
        blob = encrypt_bytes_for_tenant(b"tenant-a-data", uuid.uuid4())
        with pytest.raises(InvalidTag):
            decrypt_bytes_for_tenant(blob, uuid.uuid4())

    def test_tampered_ciphertext_fails(self):
        tid = uuid.uuid4()
        blob = bytearray(encrypt_bytes_for_tenant(b"payload", tid))
        blob[-1] ^= 0xFF
        with pytest.raises(InvalidTag):
            decrypt_bytes_for_tenant(bytes(blob), tid)
