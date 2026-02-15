from __future__ import annotations

from .base import AdapterDefaults, SiteAdapter


class SupabaseAdapter(SiteAdapter):
    name = "supabase"

    def can_handle(self, text: str) -> bool:
        return "supabase.com" in text.lower()

    def defaults(self) -> AdapterDefaults:
        return AdapterDefaults(
            target_hint="supabase.com",
            filter_host_contains="supabase.com",
            allowed_domains=["supabase.com", "api.supabase.com"],
            replay_url_contains="supabase.com",
        )


class GithubAdapter(SiteAdapter):
    name = "github"

    def can_handle(self, text: str) -> bool:
        return "github.com" in text.lower()

    def defaults(self) -> AdapterDefaults:
        return AdapterDefaults(
            target_hint="github.com",
            filter_host_contains="github.com",
            allowed_domains=["github.com", "api.github.com"],
            replay_url_contains="github.com",
        )


class GmailAdapter(SiteAdapter):
    name = "gmail"

    def can_handle(self, text: str) -> bool:
        lowered = text.lower()
        return "mail.google.com" in lowered or "gmail" in lowered

    def defaults(self) -> AdapterDefaults:
        return AdapterDefaults(
            target_hint="google.com",
            filter_host_contains="google.com",
            allowed_domains=["google.com", "mail.google.com", "accounts.google.com"],
            replay_url_contains="google.com",
        )
