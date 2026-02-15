from __future__ import annotations


class CookieMonsterError(Exception):
    """Base exception type for library consumers."""


class ConfigurationError(CookieMonsterError):
    pass


class ReplayPolicyError(CookieMonsterError):
    pass


class CaptureError(CookieMonsterError):
    pass


class ReplayError(CookieMonsterError):
    pass
