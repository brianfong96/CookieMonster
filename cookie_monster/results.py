from __future__ import annotations

from dataclasses import dataclass, field

from .models import CapturedRequest


@dataclass
class CaptureResult:
    captures: list[CapturedRequest] = field(default_factory=list)
    output_file: str = "captures.jsonl"

    @property
    def count(self) -> int:
        return len(self.captures)


@dataclass
class ReplayResult:
    status_code: int
    content_type: str
    body_preview: str
    request_url: str


@dataclass
class SessionHealthResult:
    has_cookie: bool
    bearer_token_count: int
    jwt_expired: bool | None
    jwt_expires_at: str | None
