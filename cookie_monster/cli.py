from __future__ import annotations

import argparse
import json

from .capture import capture_requests
from .config import CaptureConfig, ReplayConfig
from .replay import replay_with_capture


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cookie-monster",
        description=(
            "Capture auth headers from your own Chrome DevTools network traffic "
            "and replay requests for automation."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture_parser = subparsers.add_parser("capture", help="Capture request headers from Chrome")
    capture_parser.add_argument("--chrome-host", default="127.0.0.1")
    capture_parser.add_argument("--chrome-port", type=int, default=9222)
    capture_parser.add_argument("--duration", type=int, default=30)
    capture_parser.add_argument("--max-records", type=int, default=100)
    capture_parser.add_argument(
        "--target-hint",
        default=None,
        help="Match target tab/request URLs by substring",
    )
    capture_parser.add_argument("--output", default="captures.jsonl")
    capture_parser.add_argument(
        "--header",
        action="append",
        default=None,
        help="Repeatable header name allowlist (default captures cookie/auth headers)",
    )
    capture_parser.add_argument(
        "--include-all-headers",
        action="store_true",
        help="Store all request headers instead of only allowlisted headers",
    )

    replay_parser = subparsers.add_parser("replay", help="Replay an HTTP request from captured headers")
    replay_parser.add_argument("--capture-file", default="captures.jsonl")
    replay_parser.add_argument("--request-url", required=True)
    replay_parser.add_argument("--method", default="GET")
    replay_parser.add_argument("--url-contains", default=None)
    replay_parser.add_argument("--timeout", type=int, default=20)
    replay_parser.add_argument("--output", default=None)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "capture":
        config = CaptureConfig(
            chrome_host=args.chrome_host,
            chrome_port=args.chrome_port,
            duration_seconds=args.duration,
            max_records=args.max_records,
            target_hint=args.target_hint,
            output_file=args.output,
            header_allowlist=args.header or CaptureConfig().header_allowlist,
            include_all_headers=args.include_all_headers,
        )
        captures = capture_requests(config)
        print(json.dumps({"captured": len(captures), "output": config.output_file}, indent=2))
        return

    if args.command == "replay":
        config = ReplayConfig(
            capture_file=args.capture_file,
            request_url=args.request_url,
            method=args.method,
            url_contains=args.url_contains,
            timeout_seconds=args.timeout,
            output_file=args.output,
        )
        response = replay_with_capture(config)
        print(
            json.dumps(
                {
                    "status_code": response.status_code,
                    "content_type": response.headers.get("Content-Type", ""),
                    "body_preview": response.text[:400],
                },
                indent=2,
            )
        )
        return

    parser.error("Unknown command")


if __name__ == "__main__":
    main()
