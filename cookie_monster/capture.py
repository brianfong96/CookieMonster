from __future__ import annotations

import time
from urllib.parse import urlparse
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


def _request_matches_filters(
    url: str,
    method: str,
    resource_type: str | None,
    host_contains: str | None,
    path_contains: str | None,
    filter_method: str | None,
    filter_resource_type: str | None,
) -> bool:
    if host_contains:
        host = (urlparse(url).hostname or "").lower()
        if host_contains.lower() not in host:
            return False
    if path_contains:
        path = urlparse(url).path.lower()
        if path_contains.lower() not in path:
            return False
    if filter_method and method.upper() != filter_method.upper():
        return False
    if filter_resource_type and (resource_type or "").lower() != filter_resource_type.lower():
        return False
    return True


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
                req_method = str(request.get("method", "GET"))
                req_resource_type = str(params.get("type")) if params.get("type") is not None else None
                if not _request_matches_filters(
                    url=url,
                    method=req_method,
                    resource_type=req_resource_type,
                    host_contains=config.filter_host_contains,
                    path_contains=config.filter_path_contains,
                    filter_method=config.filter_method,
                    filter_resource_type=config.filter_resource_type,
                ):
                    continue

                state = request_state.setdefault(request_id, {})
                state["request_id"] = request_id
                state["method"] = req_method
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
                if not _request_matches_filters(
                    url=url,
                    method=str(state.get("method", "GET")),
                    resource_type=(
                        str(state["resource_type"]) if state.get("resource_type") is not None else None
                    ),
                    host_contains=config.filter_host_contains,
                    path_contains=config.filter_path_contains,
                    filter_method=config.filter_method,
                    filter_resource_type=config.filter_resource_type,
                ):
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
        append_captures(config.output_file, captured, encryption_key=config.encryption_key)
    return captured
