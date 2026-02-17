"""CookieMonster package."""

from .client import CookieMonsterClient
from .config import CaptureConfig, ReplayConfig
from .models import CapturedRequest
from .tab_manager import TabHandle, TabManager, TabManagerConfig

__all__ = [
    "CapturedRequest",
    "CaptureConfig",
    "ReplayConfig",
    "CookieMonsterClient",
    "TabHandle",
    "TabManager",
    "TabManagerConfig",
]
