from __future__ import annotations

import argparse
import json
from importlib.metadata import PackageNotFoundError, version
from subprocess import Popen

from .capture import capture_requests
from .chrome_launcher import launch_browser, wait_for_debug_endpoint
from .config import CaptureConfig, ReplayConfig
from .replay import replay_with_capture


def _tool_version() -> str:
    try:
        return version("cookie-monster-cli")
    except PackageNotFoundError:
        return "0.0.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cookie-monster",
        description=(
            "Capture auth headers from your own Chrome DevTools network traffic "
            "and replay requests for automation."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {_tool_version()}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture_parser = subparsers.add_parser("capture", help="Capture request headers from Chrome")
    capture_parser.add_argument("--chrome-host", default="127.0.0.1")
    capture_parser.add_argument("--chrome-port", type=int, default=9222)
    capture_parser.add_argument(
        "--browser",
        default="chrome",
        choices=["chrome", "edge"],
        help="Browser to launch when using --launch-browser",
    )
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
    capture_parser.add_argument(
        "--launch-browser",
        action="store_true",
        help="Launch browser from this command before capture",
    )
    capture_parser.add_argument(
        "--launch-chrome",
        action="store_true",
        help="Deprecated alias for --launch-browser",
    )
    capture_parser.add_argument("--browser-path", default=None, help="Path to browser executable")
    capture_parser.add_argument(
        "--chrome-path",
        default=None,
        help="Deprecated alias for --browser-path (kept for compatibility)",
    )
    capture_parser.add_argument("--user-data-dir", default=None, help="Browser user data dir root")
    capture_parser.add_argument(
        "--profile-directory",
        default=None,
        help="Browser profile directory inside user data dir (e.g. Default, Profile 1)",
    )
    capture_parser.add_argument("--open-url", default=None, help="URL to open when launching browser")
    capture_parser.add_argument("--headless", action="store_true", help="Run launched browser in headless mode")
    capture_parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Do not terminate Chrome after capture when --launch-chrome is used",
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
    launched_proc: Popen[bytes] | None = None

    if args.command == "capture":
        if args.launch_chrome or args.launch_browser:
            launched_proc = launch_browser(
                browser=args.browser,
                browser_path=args.browser_path or args.chrome_path,
                host=args.chrome_host,
                port=args.chrome_port,
                user_data_dir=args.user_data_dir,
                profile_directory=args.profile_directory,
                open_url=args.open_url,
                headless=args.headless,
            )
            wait_for_debug_endpoint(args.chrome_host, args.chrome_port)

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
        try:
            captures = capture_requests(config)
            print(json.dumps({"captured": len(captures), "output": config.output_file}, indent=2))
        finally:
            if launched_proc is not None and not args.keep_open:
                launched_proc.terminate()
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
