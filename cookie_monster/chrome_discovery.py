from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request


def _read_json(url: str) -> list[dict] | dict:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def list_targets(host: str, port: int, retries: int = 1, retry_delay_seconds: float = 0.5) -> list[dict]:
    endpoint = f"http://{host}:{port}/json"
    last_error: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            data = _read_json(endpoint)
            if not isinstance(data, list):
                raise RuntimeError("Unexpected /json response from Chrome DevTools endpoint")
            return data
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < retries - 1:
                time.sleep(retry_delay_seconds)

    raise RuntimeError(
        f"Could not reach Chrome DevTools at {endpoint}. "
        "Start Chrome with --remote-debugging-port and try again."
    ) from last_error


def pick_target(host: str, port: int, hint: str | None = None) -> dict:
    targets = [t for t in list_targets(host, port, retries=8, retry_delay_seconds=0.5) if t.get("type") == "page"]
    if not targets:
        raise RuntimeError(
            "No page targets found. Open a tab in the Chrome instance started with --remote-debugging-port."
        )

    if hint:
        lowered = hint.lower()
        for target in targets:
            url = str(target.get("url", "")).lower()
            title = str(target.get("title", "")).lower()
            if lowered in url or lowered in title:
                return target

    return targets[0]


def get_websocket_debug_url(host: str, port: int, hint: str | None = None) -> str:
    target = pick_target(host, port, hint)
    ws_url = target.get("webSocketDebuggerUrl")
    if not ws_url:
        target_id = urllib.parse.quote(str(target.get("id", "")))
        if not target_id:
            raise RuntimeError("Target missing webSocketDebuggerUrl and id")
        ws_url = f"ws://{host}:{port}/devtools/page/{target_id}"
    return str(ws_url)
