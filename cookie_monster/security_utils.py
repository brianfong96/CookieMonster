from __future__ import annotations

from urllib.parse import urlparse

SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "apikey",
    "x-auth-token",
    "proxy-authorization",
}


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted: dict[str, str] = {}
    for k, v in headers.items():
        if k.lower() in SENSITIVE_HEADERS:
            redacted[k] = "***REDACTED***"
        else:
            redacted[k] = v
    return redacted


def url_host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def enforce_allowed_domain(url: str, allowed_domains: list[str]) -> None:
    if not allowed_domains:
        return
    host = url_host(url)
    allowed = [d.lower().strip() for d in allowed_domains if d.strip()]
    if any(host == d or host.endswith(f".{d}") for d in allowed):
        return
    raise RuntimeError(
        f"Refusing replay to host '{host}'. Add host to --allowed-domain to permit this target."
    )
