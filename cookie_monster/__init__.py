"""CookieMonster package."""

from .browser_profiles import resolve_profile
from .capture import audience_domain, extract_token_details, extract_tokens
from .chrome_launcher import browser_is_reachable, is_browser_process_running
from .client import CookieMonsterClient
from .config import CaptureConfig, ReplayConfig
from .models import CapturedRequest
from .tab_manager import TabHandle, TabManager, TabManagerConfig

__all__ = [
    "CapturedRequest",
    "CaptureConfig",
    "CookieMonsterClient",
    "ReplayConfig",
    "TabHandle",
    "TabManager",
    "TabManagerConfig",
    "audience_domain",
    "browser_is_reachable",
    "extract_token_details",
    "extract_tokens",
    "is_browser_process_running",
    "resolve_profile",
]
