from __future__ import annotations

import base64
import json
from datetime import UTC, datetime

from .models import CapturedRequest
from .results import SessionHealthResult


def _decode_jwt_exp(token: str) -> datetime | None:
    parts = token.split(".")
    if len(parts) < 2:
        return None
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode((payload + padding).encode("utf-8"))
        obj = json.loads(decoded.decode("utf-8"))
        exp = obj.get("exp")
        if exp is None:
            return None
        return datetime.fromtimestamp(int(exp), tz=UTC)
    except Exception:  # noqa: BLE001
        return None


def analyze_session_health(captures: list[CapturedRequest]) -> SessionHealthResult:
    has_cookie = False
    bearer_tokens: list[str] = []

    for cap in captures:
        lower = {k.lower(): str(v) for k, v in cap.headers.items()}
        if "cookie" in lower:
            has_cookie = True
        auth = lower.get("authorization", "")
        if auth.lower().startswith("bearer "):
            bearer_tokens.append(auth.split(" ", 1)[1])

    jwt_expires_at = None
    jwt_expired = None
    if bearer_tokens:
        exp = _decode_jwt_exp(bearer_tokens[-1])
        if exp is not None:
            jwt_expires_at = exp.isoformat()
            jwt_expired = exp <= datetime.now(UTC)

    return SessionHealthResult(
        has_cookie=has_cookie,
        bearer_token_count=len(bearer_tokens),
        jwt_expired=jwt_expired,
        jwt_expires_at=jwt_expires_at,
    )
