from __future__ import annotations

import os
from pathlib import Path

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


def load_or_create_key(path: str) -> str:
    key_path = Path(path)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            pass
        return key_path.read_text(encoding="utf-8").strip()
    key = Fernet.generate_key().decode("utf-8")
    key_path.write_text(key, encoding="utf-8")
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    return key
