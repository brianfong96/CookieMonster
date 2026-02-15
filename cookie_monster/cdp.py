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
