from __future__ import annotations

import json
from pathlib import Path

import requests

from .config import ReplayConfig
from .models import CapturedRequest
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
    captures = load_captures(config.capture_file)
    selected = _pick_capture(captures, config)

    headers = _sanitize_headers(selected.headers)
    response = requests.request(
        method=config.method.upper(),
        url=config.request_url,
        headers=headers,
        timeout=config.timeout_seconds,
    )

    if config.output_file:
        payload = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": response.text,
        }
        out_path = Path(config.output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return response
