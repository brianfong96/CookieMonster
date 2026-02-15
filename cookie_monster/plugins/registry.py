from __future__ import annotations

from .base import SiteAdapter
from .builtins import GithubAdapter, GmailAdapter, SupabaseAdapter

_ADAPTERS: dict[str, SiteAdapter] = {
    "supabase": SupabaseAdapter(),
    "github": GithubAdapter(),
    "gmail": GmailAdapter(),
}


def list_adapters() -> list[str]:
    return sorted(_ADAPTERS.keys())


def get_adapter(name: str) -> SiteAdapter:
    key = name.lower().strip()
    if key not in _ADAPTERS:
        raise KeyError(f"Unknown adapter '{name}'. Available: {', '.join(list_adapters())}")
    return _ADAPTERS[key]


def auto_detect_adapter(text: str) -> SiteAdapter | None:
    if not text:
        return None
    for adapter in _ADAPTERS.values():
        if adapter.can_handle(text):
            return adapter
    return None
