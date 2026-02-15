from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class CapturedRequest:
    request_id: str
    method: str
    url: str
    headers: dict[str, str]
    seen_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resource_type: str | None = None
    post_data: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "method": self.method,
            "url": self.url,
            "headers": self.headers,
            "seen_at": self.seen_at,
            "resource_type": self.resource_type,
            "post_data": self.post_data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CapturedRequest:
        return cls(
            request_id=str(data.get("request_id", "")),
            method=str(data.get("method", "GET")),
            url=str(data.get("url", "")),
            headers={str(k): str(v) for k, v in dict(data.get("headers", {})).items()},
            seen_at=str(data.get("seen_at", datetime.now(timezone.utc).isoformat())),
            resource_type=data.get("resource_type"),
            post_data=(None if data.get("post_data") is None else str(data.get("post_data"))),
        )
