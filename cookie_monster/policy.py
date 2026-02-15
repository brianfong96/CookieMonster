from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass
class ReplayPolicy:
    allowed_domains: list[str] = field(default_factory=list)
    denied_domains: list[str] = field(default_factory=list)
    deny_path_contains: list[str] = field(default_factory=list)

    def validate(self, url: str) -> None:
        host = (urlparse(url).hostname or "").lower()
        path = (urlparse(url).path or "").lower()

        denied = [d.lower().strip() for d in self.denied_domains if d.strip()]
        if any(host == d or host.endswith(f".{d}") for d in denied):
            raise RuntimeError(f"Replay blocked: domain '{host}' is denied by policy")

        allow = [d.lower().strip() for d in self.allowed_domains if d.strip()]
        if allow and not any(host == d or host.endswith(f".{d}") for d in allow):
            raise RuntimeError(f"Replay blocked: domain '{host}' is not in allowlist")

        for item in self.deny_path_contains:
            token = item.lower().strip()
            if token and token in path:
                raise RuntimeError(f"Replay blocked: path contains denied token '{token}'")
