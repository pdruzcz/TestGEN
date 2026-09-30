"""Unit tests for Argon2id password hashing."""

from app.core.security import check_needs_rehash, hash_password, verify_password


class TestPasswordHasher:
    def test_hash_password_returns_argon2id_hash(self):
        hashed = hash_password("SecurePassword123!")
        assert hashed.startswith("$argon2id$")

    def test_verify_password_correct(self):
        plain = "MyStrongP@ss12"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_password_wrong(self):
        hashed = hash_password("CorrectPassword1")
        assert verify_password("WrongPassword1", hashed) is False

    def test_verify_password_tampered_hash(self):
        assert verify_password("anything", "$argon2id$v=19$m=65536,t=3,p=4$bad$data") is False

    def test_hash_uniqueness(self):
        h1 = hash_password("SamePassword123!")
        h2 = hash_password("SamePassword123!")
        assert h1 != h2  # different salts

    def test_check_needs_rehash_fresh_hash(self):
        hashed = hash_password("TestPassword123!")
        assert check_needs_rehash(hashed) is False

    def test_verify_password_placeholder_hash_returns_false(self):
        """H5 Round 5: Placeholder hash must return False, not raise exception."""
        assert verify_password("anypassword", "!INVITATION_PENDING!") is False

    def test_verify_password_empty_hash_returns_false(self):
        assert verify_password("anypassword", "") is False
