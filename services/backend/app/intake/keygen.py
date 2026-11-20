"""CLI to generate a secure intake API key and its hash."""

from __future__ import annotations

import secrets
import sys

from argon2 import PasswordHasher


def generate_key_and_hash() -> tuple[str, str]:
    """Generate a high-entropy random key and its argon2id hash."""
    key = secrets.token_urlsafe(32)
    hasher = PasswordHasher()
    key_hash = hasher.hash(key)
    return key, key_hash


def main() -> None:
    key, key_hash = generate_key_and_hash()
    sys.stdout.write("Generated Intake API Key:\n")
    sys.stdout.write(f"Key:  {key}\n\n")
    sys.stdout.write("Intake Key Hash (set as INTAKE_KEY_HASH in settings / Key Vault):\n")
    sys.stdout.write(f"Hash: {key_hash}\n")


if __name__ == "__main__":
    main()
