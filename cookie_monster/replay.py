from __future__ import annotations

import json
import time
from pathlib import Path

import requests

from .config import ReplayConfig
from .models import CapturedRequest
from .security_utils import enforce_allowed_domain, redact_headers, url_host
from .storage import load_captures


def _pick_capture(captures: list[CapturedRequest], config: ReplayConfig) -> CapturedRequest:
    candidates = captures
    if config.url_contains:
        lowered = config.url_contains.lower()
        candidates = [c for c in candidates if lowered in c.url.lower()]

    method = config.method.upper()
    candidates = [c for c in candidates if c.method.upper() == method]

    if not candidates:
        raise RuntimeError("No captured requests matched the replay filters")

    return candidates[-1]


def _sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    blocked = {"host", "content-length", "connection"}
    return {k: v for k, v in headers.items() if k.lower() not in blocked}


def replay_with_capture(config: ReplayConfig) -> requests.Response:
    captures = load_captures(config.capture_file, encryption_key=config.encryption_key)
    selected = _pick_capture(captures, config)
    if config.enforce_capture_host and url_host(selected.url) != url_host(config.request_url):
        raise RuntimeError(
            "Refusing replay to a different host than captured request. "
            "Use --no-enforce-capture-host to override."
        )
    enforce_allowed_domain(config.request_url, config.allowed_domains)

    headers = _sanitize_headers(selected.headers)
    request_json = None
    request_data = None
    if config.json_body_file:
        request_json = json.loads(Path(config.json_body_file).read_text(encoding="utf-8"))
    elif config.body is not None:
        request_data = config.body

    max_attempts = max(1, int(config.retry_attempts))
    response: requests.Response | None = None
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.request(
                method=config.method.upper(),
                url=config.request_url,
                headers=headers,
                timeout=config.timeout_seconds,
                data=request_data,
                json=request_json,
            )
            if response.status_code < 500 or attempt == max_attempts:
                break
        except requests.RequestException as exc:
            last_error = exc
            if attempt == max_attempts:
                raise
        if attempt < max_attempts:
            time.sleep(max(0.0, float(config.retry_backoff_seconds)))

    if response is None:
        if last_error is not None:
            raise last_error
        raise RuntimeError("Replay failed without a response")

    if config.output_file:
        out_headers = dict(response.headers)
        in_headers = headers
        if config.redact_output:
            out_headers = redact_headers(out_headers)
            in_headers = redact_headers(in_headers)
        payload = {
            "status_code": response.status_code,
            "request_headers": in_headers,
            "headers": out_headers,
            "body": response.text,
        }
        out_path = Path(config.output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return response
