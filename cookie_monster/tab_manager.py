"""Manage long-lived browser tabs: open, refresh, navigate, and close."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .cdp import CDPClient
from .chrome_discovery import get_websocket_debug_url, list_page_targets

logger = logging.getLogger(__name__)


@dataclass
class TabHandle:
    """Lightweight reference to a browser tab."""

    target_id: str
    url: str
    title: str
    ws_url: str


@dataclass
class TabManagerConfig:
    """Settings that control how :class:`TabManager` connects to a browser."""

    chrome_host: str = "127.0.0.1"
    chrome_port: int = 9222
    load_timeout_seconds: float = 30.0
    ignore_cache: bool = False


class TabManager:
    """Keep tabs alive and navigate or refresh them without tearing them down.

    Usage::

        mgr = TabManager(TabManagerConfig())
        tabs = mgr.list_tabs()
        mgr.refresh(tabs[0].target_id)
        mgr.navigate(tabs[0].target_id, "https://example.com")
        mgr.close()
    """

    def __init__(self, config: TabManagerConfig | None = None) -> None:
        self.config = config or TabManagerConfig()
        self._clients: dict[str, CDPClient] = {}

    # ---- internal helpers ----

    def _ws_url_for_target(self, target_id: str) -> str:
        host = self.config.chrome_host
        port = self.config.chrome_port
        return f"ws://{host}:{port}/devtools/page/{target_id}"

    def _get_client(self, target_id: str) -> CDPClient:
        """Return (and cache) a connected :class:`CDPClient` for *target_id*."""
        client = self._clients.get(target_id)
        if client is not None:
            return client
        ws_url = self._ws_url_for_target(target_id)
        client = CDPClient(ws_url)
        client.connect()
        client.enable_page_events()
        self._clients[target_id] = client
        return client

    def _drop_client(self, target_id: str) -> None:
        client = self._clients.pop(target_id, None)
        if client is not None:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass

    # ---- public API ----

    def list_tabs(self) -> list[TabHandle]:
        """Return every ``page`` target currently open in the browser."""
        targets = list_page_targets(self.config.chrome_host, self.config.chrome_port)
        return [
            TabHandle(
                target_id=str(t.get("id", "")),
                url=str(t.get("url", "")),
                title=str(t.get("title", "")),
                ws_url=str(
                    t.get("webSocketDebuggerUrl", self._ws_url_for_target(str(t.get("id", ""))))
                ),
            )
            for t in targets
        ]

    def open_tab(self, url: str = "about:blank") -> TabHandle:
        """Create a new tab (via the browser endpoint) and return a handle."""
        # Use an existing client (any tab) to send Target.createTarget, or
        # fall back to the HTTP JSON endpoint.
        tabs = self.list_tabs()
        if tabs:
            client = self._get_client(tabs[0].target_id)
            target_id = client.create_target(url)
        else:
            # No tabs – open via the HTTP endpoint which always exists
            import json
            import urllib.request

            endpoint = (
                f"http://{self.config.chrome_host}:{self.config.chrome_port}"
                f"/json/new?{url}"
            )
            with urllib.request.urlopen(endpoint, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                target_id = str(data.get("id", ""))

        handle = TabHandle(
            target_id=target_id,
            url=url,
            title="",
            ws_url=self._ws_url_for_target(target_id),
        )
        logger.info("Opened tab %s → %s", target_id, url)
        return handle

    def refresh(self, target_id: str, *, ignore_cache: bool | None = None) -> bool:
        """Reload the page in an existing tab. Returns ``True`` when the load event fires."""
        use_ignore_cache = ignore_cache if ignore_cache is not None else self.config.ignore_cache
        client = self._get_client(target_id)
        client.reload(ignore_cache=use_ignore_cache)
        loaded = client.wait_for_load(timeout_seconds=self.config.load_timeout_seconds)
        logger.info("Refreshed tab %s (loaded=%s)", target_id, loaded)
        return loaded

    def navigate(self, target_id: str, url: str) -> bool:
        """Navigate an existing tab to *url*. Returns ``True`` when the load event fires."""
        client = self._get_client(target_id)
        client.navigate(url)
        loaded = client.wait_for_load(timeout_seconds=self.config.load_timeout_seconds)
        logger.info("Navigated tab %s → %s (loaded=%s)", target_id, url, loaded)
        return loaded

    def close_tab(self, target_id: str) -> bool:
        """Close a specific tab and drop any cached CDP connection."""
        tabs = self.list_tabs()
        if tabs:
            client = self._get_client(tabs[0].target_id)
            success = client.close_target(target_id)
        else:
            success = False
        self._drop_client(target_id)
        logger.info("Closed tab %s (success=%s)", target_id, success)
        return success

    def close(self) -> None:
        """Disconnect all cached CDP clients (does **not** close the tabs)."""
        for target_id in list(self._clients):
            self._drop_client(target_id)

    # ---- context-manager support ----

    def __enter__(self) -> TabManager:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        self.close()
        return False
