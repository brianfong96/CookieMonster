from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

from .cdp import CDPClient
from .chrome_discovery import get_websocket_debug_url
from .config import CaptureConfig
from .models import CapturedRequest
from .storage import append_captures
from .tab_manager import TabManager, TabManagerConfig


def _normalize_headers(headers: dict[str, Any]) -> dict[str, str]:
    return {str(k): str(v) for k, v in headers.items()}


def _normalize_post_data(value: Any, max_bytes: int) -> str | None:
    if value is None:
        return None
    raw = str(value).encode("utf-8")
    if len(raw) <= max_bytes:
        return str(value)
    return raw[:max_bytes].decode("utf-8", errors="ignore")


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


def _refresh_target_tab(config: CaptureConfig) -> None:
    """Refresh the browser tab that matches the capture target so new network
    traffic is generated without manually interacting with the browser."""
    mgr_config = TabManagerConfig(
        chrome_host=config.chrome_host,
        chrome_port=config.chrome_port,
        ignore_cache=config.ignore_cache,
    )
    with TabManager(mgr_config) as mgr:
        target_id = config.refresh_target_id
        if not target_id:
            tabs = mgr.list_tabs()
            if config.target_hint:
                lowered = config.target_hint.lower()
                matched = [
                    t for t in tabs
                    if lowered in t.url.lower() or lowered in t.title.lower()
                ]
                if matched:
                    target_id = matched[0].target_id
            if not target_id and tabs:
                target_id = tabs[0].target_id
        if target_id:
            mgr.refresh(target_id, ignore_cache=config.ignore_cache)


def capture_requests(config: CaptureConfig) -> list[CapturedRequest]:
    ws_url = get_websocket_debug_url(config.chrome_host, config.chrome_port, config.target_hint)
    client = CDPClient(ws_url)
    request_state: dict[str, dict[str, Any]] = {}
    captured: list[CapturedRequest] = []
    emitted_request_ids: set[str] = set()

    client.connect()
    try:
        client.send_command("Network.enable", {})

        # If --refresh-tab is set, refresh the matched tab to trigger network
        # traffic instead of waiting for the user to navigate manually.
        if config.refresh_tab:
            _refresh_target_tab(config)

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
                if config.capture_post_data:
                    state["post_data"] = _normalize_post_data(
                        request.get("postData"), max(0, int(config.max_post_data_bytes))
                    )
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

                post_data = None
                if config.capture_post_data:
                    post_data = (
                        str(state["post_data"])
                        if state.get("post_data") is not None
                        else None
                    )
                    if post_data is None:
                        try:
                            result = client.send_command(
                                "Network.getRequestPostData",
                                {"requestId": request_id},
                            )
                            post_data = _normalize_post_data(
                                result.get("postData"),
                                max(0, int(config.max_post_data_bytes)),
                            )
                        except Exception:  # noqa: BLE001
                            post_data = None

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
                    post_data=post_data,
                )
                captured.append(capture)
                emitted_request_ids.add(request_id)

    finally:
        client.close()

    if captured:
        append_captures(config.output_file, captured, encryption_key=config.encryption_key)
    return captured
