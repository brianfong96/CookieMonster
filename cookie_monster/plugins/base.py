from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AdapterDefaults:
    target_hint: str | None = None
    filter_host_contains: str | None = None
    filter_path_contains: str | None = None
    allowed_domains: list[str] = field(default_factory=list)
    replay_url_contains: str | None = None


class SiteAdapter:
    name: str = "generic"

    def can_handle(self, text: str) -> bool:
        return False

    def defaults(self) -> AdapterDefaults:
        return AdapterDefaults()
