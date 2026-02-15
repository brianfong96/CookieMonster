from __future__ import annotations

import time
from typing import Any

from .cdp import CDPClient
from .chrome_discovery import get_websocket_debug_url
from .config import CaptureConfig
from .models import CapturedRequest
from .storage import append_captures


def _normalize_headers(headers: dict[str, Any]) -> dict[str, str]:
    return {str(k): str(v) for k, v in headers.items()}


def _filter_headers(
    headers: dict[str, str],
    allowlist: list[str],
    include_all_headers: bool,
) -> dict[str, str]:
    if include_all_headers:
        return headers

    allowed = {h.lower() for h in allowlist}
    return {k: v for k, v in headers.items() if k.lower() in allowed}


def capture_requests(config: CaptureConfig) -> list[CapturedRequest]:
    ws_url = get_websocket_debug_url(config.chrome_host, config.chrome_port, config.target_hint)
    client = CDPClient(ws_url)
    request_state: dict[str, dict[str, Any]] = {}
    captured: list[CapturedRequest] = []
    emitted_request_ids: set[str] = set()

    client.connect()
    try:
        client.send_command("Network.enable", {})

        deadline = time.time() + config.duration_seconds
        while time.time() < deadline and len(captured) < config.max_records:
            message = client.read_event(timeout_seconds=1.0)
            if not message:
                continue

            method = str(message.get("method", ""))
            params = dict(message.get("params", {}))

            if method == "Network.requestWillBeSent":
                request_id = str(params.get("requestId", ""))
                request = dict(params.get("request", {}))
                url = str(request.get("url", ""))
                if config.target_hint and config.target_hint.lower() not in url.lower():
                    continue

                state = request_state.setdefault(request_id, {})
                state["request_id"] = request_id
                state["method"] = str(request.get("method", "GET"))
                state["url"] = url
                state["resource_type"] = params.get("type")
                state.setdefault("headers", {}).update(
                    _normalize_headers(dict(request.get("headers", {})))
                )

            elif method == "Network.requestWillBeSentExtraInfo":
                request_id = str(params.get("requestId", ""))
                state = request_state.setdefault(request_id, {"request_id": request_id})
                state.setdefault("headers", {}).update(
                    _normalize_headers(dict(params.get("headers", {})))
                )

            for request_id, state in list(request_state.items()):
                if request_id in emitted_request_ids:
                    continue
                headers = dict(state.get("headers", {}))
                if not headers:
                    continue

                filtered = _filter_headers(headers, config.header_allowlist, config.include_all_headers)
                if not filtered:
                    continue

                url = str(state.get("url", ""))
                if config.target_hint and config.target_hint.lower() not in url.lower():
                    continue

                capture = CapturedRequest(
                    request_id=request_id,
                    method=str(state.get("method", "GET")),
                    url=url,
                    headers=filtered,
                    resource_type=(
                        str(state["resource_type"])
                        if state.get("resource_type") is not None
                        else None
                    ),
                )
                captured.append(capture)
                emitted_request_ids.add(request_id)

    finally:
        client.close()

    if captured:
        append_captures(config.output_file, captured)
    return captured
