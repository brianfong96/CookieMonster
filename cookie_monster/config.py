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
    filter_host_contains: str | None = None
    filter_path_contains: str | None = None
    filter_method: str | None = None
    filter_resource_type: str | None = None
    encryption_key: str | None = None


@dataclass
class ReplayConfig:
    capture_file: str
    request_url: str
    method: str = "GET"
    url_contains: str | None = None
    timeout_seconds: int = 20
    output_file: str | None = None
    body: str | None = None
    json_body_file: str | None = None
    retry_attempts: int = 1
    retry_backoff_seconds: float = 0.5
    allowed_domains: list[str] = field(default_factory=list)
    redact_output: bool = False
    enforce_capture_host: bool = True
    encryption_key: str | None = None
