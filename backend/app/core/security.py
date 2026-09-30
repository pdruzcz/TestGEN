"""Argon2id password hashing per OWASP recommendations.

Haszowanie kluczy API (Story 8.6) celowo używa SHA-256, nie Argon2id:
klucz to 256 bitów losowości z ``secrets``, więc atak słownikowy nie ma
czego zgadywać, a hash liczony jest przy **każdym** requeście z CI/CD.
"""

import hashlib

from argon2 import PasswordHasher as _Argon2Hasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = _Argon2Hasher(
    time_cost=3,
    memory_cost=65536,  # 64 MB
    parallelism=4,
    hash_len=32,
)


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        # InvalidHashError covers placeholder hashes like "!INVITATION_PENDING!"
        return False


def check_needs_rehash(hashed: str) -> bool:
    return _hasher.check_needs_rehash(hashed)


def hash_api_key(key: str) -> str:
    """SHA-256 klucza API w hex — deterministyczne, do lookupu w ``api_keys``."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
