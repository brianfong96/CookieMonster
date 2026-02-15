from __future__ import annotations

import json
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .capture import capture_requests
from .chrome_discovery import list_page_targets
from .config import CaptureConfig, ReplayConfig
from .replay import replay_with_capture


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
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
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

            _json_response(self, 404, {"error": "Not found"})

    return Handler


def serve_api(host: str = "127.0.0.1", port: int = 8787) -> None:
    server = ThreadingHTTPServer((host, port), make_handler())
    server.serve_forever()
