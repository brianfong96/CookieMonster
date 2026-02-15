from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_HEADER_ALLOWLIST = [
    "cookie",
    "authorization",
    "x-csrf-token",
    "x-xsrf-token",
]


@dataclass
class CaptureConfig:
    chrome_host: str = "127.0.0.1"
    chrome_port: int = 9222
    duration_seconds: int = 30
    max_records: int = 100
    target_hint: str | None = None
    output_file: str = "captures.jsonl"
    header_allowlist: list[str] = field(default_factory=lambda: list(DEFAULT_HEADER_ALLOWLIST))
    include_all_headers: bool = False


@dataclass
class ReplayConfig:
    capture_file: str
    request_url: str
    method: str = "GET"
    url_contains: str | None = None
    timeout_seconds: int = 20
    output_file: str | None = None
