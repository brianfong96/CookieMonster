from __future__ import annotations

import json
from itertools import count
from typing import Any

from websocket import (
    WebSocket,
    WebSocketBadStatusException,
    WebSocketTimeoutException,
    create_connection,
)


class CDPClient:
    def __init__(self, websocket_url: str, timeout_seconds: int = 10) -> None:
        self.websocket_url = websocket_url
        self.timeout_seconds = timeout_seconds
        self._next_id = count(1)
        self._ws: WebSocket | None = None

    def connect(self) -> None:
        try:
            self._ws = create_connection(self.websocket_url, timeout=self.timeout_seconds)
        except WebSocketBadStatusException as exc:
            raise RuntimeError(
                "Failed to connect to Chrome DevTools websocket. "
                "Start Chrome with --remote-allow-origins=* and --remote-debugging-port."
            ) from exc

    def close(self) -> None:
        if self._ws is not None:
            self._ws.close()
            self._ws = None

    def send_command(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._ws is None:
            raise RuntimeError("CDP client is not connected")

        msg_id = next(self._next_id)
        payload = {"id": msg_id, "method": method, "params": params or {}}
        self._ws.send(json.dumps(payload))

        while True:
            raw = self._ws.recv()
            message = json.loads(raw)
            if message.get("id") == msg_id:
                if "error" in message:
                    raise RuntimeError(f"CDP command failed: {message['error']}")
                return dict(message.get("result", {}))

    def read_event(self, timeout_seconds: float = 1.0) -> dict[str, Any] | None:
        if self._ws is None:
            raise RuntimeError("CDP client is not connected")
        self._ws.settimeout(timeout_seconds)
        try:
            raw = self._ws.recv()
        except WebSocketTimeoutException:
            return None
        message = json.loads(raw)
        if "method" not in message:
            return None
        return message

    # ---- Page helpers ----

    def navigate(self, url: str) -> dict[str, Any]:
        """Navigate the attached page to *url* (``Page.navigate``)."""
        return self.send_command("Page.navigate", {"url": url})

    def reload(self, ignore_cache: bool = False) -> dict[str, Any]:
        """Reload the current page (``Page.reload``)."""
        return self.send_command("Page.reload", {"ignoreCache": ignore_cache})

    def wait_for_load(self, timeout_seconds: float = 30.0) -> bool:
        """Block until a ``Page.loadEventFired`` event arrives or *timeout_seconds* elapses."""
        import time

        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            remaining = max(0.1, deadline - time.time())
            event = self.read_event(timeout_seconds=min(remaining, 1.0))
            if event and event.get("method") == "Page.loadEventFired":
                return True
        return False

    def enable_page_events(self) -> dict[str, Any]:
        """Enable the Page domain so load/navigation events are emitted."""
        return self.send_command("Page.enable", {})

    # ---- Target / tab helpers ----

    def create_target(self, url: str = "about:blank") -> str:
        """Create a new tab and return its *targetId*."""
        result = self.send_command("Target.createTarget", {"url": url})
        return str(result.get("targetId", ""))

    def close_target(self, target_id: str) -> bool:
        """Close the tab identified by *target_id*."""
        result = self.send_command("Target.closeTarget", {"targetId": target_id})
        return bool(result.get("success", False))

    def get_targets(self) -> list[dict[str, Any]]:
        """Return a list of all targets (tabs) known by the browser."""
        result = self.send_command("Target.getTargets", {})
        return list(result.get("targetInfos", []))
