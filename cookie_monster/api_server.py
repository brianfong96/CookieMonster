from __future__ import annotations

import json
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .capture import capture_requests
from .browser_profiles import default_user_data_dir
from .browser_session import BrowserLaunchConfig, BrowserSession
from .chrome_discovery import list_page_targets
from .diffing import compare_capture_files
from .config import CaptureConfig, ReplayConfig
from .crypto import load_or_create_key, resolve_key
from .plugins import auto_detect_adapter
from .replay import replay_with_capture
from .session_health import analyze_session_health
from .security_utils import redact_headers, url_host
from .storage import load_captures
from .ui import logo_svg, page_html


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    data = handler.rfile.read(length) if length > 0 else b"{}"
    return json.loads(data.decode("utf-8"))


def make_handler() -> type[BaseHTTPRequestHandler]:
    state_dir = Path.home() / ".cookie_monster" / "ui"
    state_dir.mkdir(parents=True, exist_ok=True)
    default_capture_file = state_dir / "captures.enc.jsonl"
    default_key_file = state_dir / "key.txt"

    def _ui_key(payload: dict) -> str:
        explicit = resolve_key(payload.get("encryption_key"), payload.get("encryption_key_env", "COOKIE_MONSTER_ENCRYPTION_KEY"))
        if explicit:
            return explicit
        return load_or_create_key(str(default_key_file))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/ui":
                html = page_html().encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)
                return
            if parsed.path == "/ui/logo.svg":
                svg = logo_svg().encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml")
                self.send_header("Content-Length", str(len(svg)))
                self.end_headers()
                self.wfile.write(svg)
                return
            if parsed.path == "/health":
                _json_response(self, 200, {"ok": True})
                return
            if parsed.path == "/targets":
                try:
                    targets = list_page_targets("127.0.0.1", 9222)
                    _json_response(self, 200, {"targets": targets})
                except Exception as exc:  # noqa: BLE001
                    _json_response(self, 500, {"error": str(exc)})
                return
            if parsed.path == "/session-health":
                try:
                    # GET /session-health?capture_file=... is intentionally omitted; use POST for explicit body.
                    _json_response(self, 400, {"error": "Use POST /session-health with JSON body"})
                except Exception as exc:  # noqa: BLE001
                    _json_response(self, 500, {"error": str(exc)})
                return
            _json_response(self, 404, {"error": "Not found"})

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            try:
                payload = _read_json_body(self)
            except Exception as exc:  # noqa: BLE001
                _json_response(self, 400, {"error": f"Invalid JSON: {exc}"})
                return

            if parsed.path == "/capture":
                try:
                    config = CaptureConfig(**payload)
                    captures = capture_requests(config)
                    _json_response(
                        self,
                        200,
                        {
                            "captured": len(captures),
                            "output": config.output_file,
                            "sample": [c.to_dict() for c in captures[:3]],
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    _json_response(self, 500, {"error": str(exc)})
                return

            if parsed.path == "/replay":
                try:
                    config = ReplayConfig(**payload)
                    response = replay_with_capture(config)
                    _json_response(
                        self,
                        200,
                        {
                            "status_code": response.status_code,
                            "content_type": response.headers.get("Content-Type", ""),
                            "body_preview": response.text[:400],
                            "config": asdict(config),
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    _json_response(self, 500, {"error": str(exc)})
                return

            if parsed.path == "/session-health":
                try:
                    capture_file = str(payload["capture_file"])
                    key = resolve_key(payload.get("encryption_key"), payload.get("encryption_key_env", "COOKIE_MONSTER_ENCRYPTION_KEY"))
                    captures = load_captures(capture_file, encryption_key=key)
                    health = analyze_session_health(captures)
                    _json_response(
                        self,
                        200,
                        {
                            "has_cookie": health.has_cookie,
                            "bearer_token_count": health.bearer_token_count,
                            "jwt_expired": health.jwt_expired,
                            "jwt_expires_at": health.jwt_expires_at,
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    _json_response(self, 500, {"error": str(exc)})
                return

            if parsed.path == "/diff":
                try:
                    diff = compare_capture_files(
                        str(payload["a"]),
                        str(payload["b"]),
                        encryption_key_a=payload.get("a_key"),
                        encryption_key_b=payload.get("b_key"),
                    )
                    _json_response(
                        self,
                        200,
                        {
                            "headers_added": diff.headers_added,
                            "headers_removed": diff.headers_removed,
                            "method_changed": diff.method_changed,
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    _json_response(self, 500, {"error": str(exc)})
                return

            if parsed.path == "/ui/cache-auth":
                try:
                    target_url = str(payload["url"])
                    browser = str(payload.get("browser", "chrome"))
                    profile_directory = str(payload.get("profile_directory", "Default"))
                    user_data_dir = payload.get("user_data_dir") or default_user_data_dir(browser)
                    if not user_data_dir:
                        raise RuntimeError("Could not determine browser user_data_dir; provide user_data_dir")

                    key = _ui_key(payload)
                    adapter = auto_detect_adapter(target_url)
                    defaults = adapter.defaults() if adapter else None

                    with BrowserSession(
                        BrowserLaunchConfig(
                            browser=browser,
                            user_data_dir=str(user_data_dir),
                            profile_directory=profile_directory,
                            open_url=target_url,
                            headless=bool(payload.get("headless", False)),
                        )
                    ):
                        captures = capture_requests(
                            CaptureConfig(
                                duration_seconds=int(payload.get("duration_seconds", 12)),
                                max_records=int(payload.get("max_records", 100)),
                                target_hint=(defaults.target_hint if defaults else url_host(target_url)),
                                include_all_headers=True,
                                filter_host_contains=(defaults.filter_host_contains if defaults else url_host(target_url)),
                                output_file=str(payload.get("capture_file") or default_capture_file),
                                encryption_key=key,
                            )
                        )
                    _json_response(
                        self,
                        200,
                        {
                            "captured": len(captures),
                            "capture_file": str(payload.get("capture_file") or default_capture_file),
                            "encrypted": True,
                            "adapter": adapter.name if adapter else None,
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    _json_response(self, 500, {"error": str(exc)})
                return

            if parsed.path == "/ui/check-auth":
                try:
                    target_url = str(payload["url"])
                    host = url_host(target_url)
                    key = _ui_key(payload)
                    capture_file = str(payload.get("capture_file") or default_capture_file)
                    captures = load_captures(capture_file, encryption_key=key)
                    matched = [c for c in captures if host in url_host(c.url)]
                    auth_count = 0
                    for c in matched:
                        lower = {k.lower() for k in c.headers}
                        if "authorization" in lower or "cookie" in lower:
                            auth_count += 1
                    _json_response(
                        self,
                        200,
                        {
                            "url_host": host,
                            "capture_file": capture_file,
                            "matched_records": len(matched),
                            "records_with_auth_headers": auth_count,
                            "has_cached_auth": auth_count > 0,
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    _json_response(self, 500, {"error": str(exc)})
                return

            if parsed.path == "/ui/inspect-auth":
                try:
                    target_url = str(payload["url"])
                    host = url_host(target_url)
                    key = _ui_key(payload)
                    capture_file = str(payload.get("capture_file") or default_capture_file)
                    captures = load_captures(capture_file, encryption_key=key)
                    matched = [c for c in captures if host in url_host(c.url)]
                    def has_auth_headers(cap) -> bool:
                        lower = {k.lower() for k in cap.headers.keys()}
                        return "authorization" in lower or "cookie" in lower
                    prioritized = [c for c in matched if has_auth_headers(c)]
                    if not prioritized:
                        prioritized = matched
                    out = []
                    for c in prioritized[-20:]:
                        item = c.to_dict()
                        item["headers"] = redact_headers(dict(item.get("headers", {})))
                        out.append(item)
                    _json_response(self, 200, {"url_host": host, "capture_file": capture_file, "records": out})
                except Exception as exc:  # noqa: BLE001
                    _json_response(self, 500, {"error": str(exc)})
                return

            _json_response(self, 404, {"error": "Not found"})

    return Handler


def serve_api(host: str = "127.0.0.1", port: int = 8787) -> None:
    server = ThreadingHTTPServer((host, port), make_handler())
    server.serve_forever()
