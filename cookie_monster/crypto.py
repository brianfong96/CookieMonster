from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken

ENCRYPTED_PREFIX = "ENC:"


def resolve_key(explicit_key: str | None, key_env_var: str = "COOKIE_MONSTER_ENCRYPTION_KEY") -> str | None:
    if explicit_key:
        return explicit_key.strip()
    env_value = os.getenv(key_env_var)
    return env_value.strip() if env_value else None


def encrypt_text(plaintext: str, key: str) -> str:
    token = Fernet(key.encode("utf-8")).encrypt(plaintext.encode("utf-8")).decode("utf-8")
    return f"{ENCRYPTED_PREFIX}{token}"


def decrypt_text(ciphertext: str, key: str) -> str:
    if not ciphertext.startswith(ENCRYPTED_PREFIX):
        return ciphertext
    token = ciphertext[len(ENCRYPTED_PREFIX) :]
    try:
        return Fernet(key.encode("utf-8")).decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Invalid encryption key for encrypted capture file") from exc
