"""Generate RSA key pair for JWT RS256 signing.

WARNING: This script generates UNENCRYPTED keys for LOCAL DEVELOPMENT ONLY.
In production, use a secrets vault (e.g., HashiCorp Vault, AWS KMS, Azure Key Vault)
to manage JWT signing keys. Never store unencrypted private keys on disk in production.
"""

import os
import stat
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_rsa_keys(output_dir: Path = Path("keys")) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_path = output_dir / "private.pem"
    public_path = output_dir / "public.pem"

    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)

    # Restrict private key file permissions (owner read-only)
    if sys.platform != "win32":
        os.chmod(private_path, stat.S_IRUSR)

    print(f"Private key: {private_path}")
    print(f"Public key:  {public_path}")
    print(
        "\nWARNING: These keys are for DEVELOPMENT ONLY. Use a secrets vault (Vault, KMS) in production.",
    )


if __name__ == "__main__":
    generate_rsa_keys()
