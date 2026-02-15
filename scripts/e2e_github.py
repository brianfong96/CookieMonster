from __future__ import annotations

import argparse
import tempfile

from cookie_monster.capture import capture_requests
from cookie_monster.chrome_launcher import detect_browser_path, launch_browser, wait_for_debug_endpoint
from cookie_monster.config import CaptureConfig, ReplayConfig
from cookie_monster.replay import replay_with_capture


def main() -> None:
    parser = argparse.ArgumentParser(description="E2E smoke test with browser + target site")
    parser.add_argument("--browser", default="chrome", choices=["chrome", "edge"])
    parser.add_argument("--browser-path", default=None)
    parser.add_argument("--chrome-path", default=None, help="Deprecated alias for --browser-path")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9222)
    parser.add_argument("--duration", type=int, default=25)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--user-data-dir", default=None)
    parser.add_argument("--keep-open", action="store_true")
    parser.add_argument("--capture-file", default="/tmp/cookie-monster-github-captures.jsonl")
    parser.add_argument("--target-url", default="https://github.com/")
    parser.add_argument("--target-hint", default="github.com")
    parser.add_argument("--replay-url", default="https://github.com/settings/profile")
    parser.add_argument("--url-contains", default="github.com")
    parser.add_argument("--response-file", default="/tmp/cookie-monster-github-response.json")
    parser.add_argument("--include-all-headers", action="store_true")
    args = parser.parse_args()

    browser_path = args.browser_path or args.chrome_path or detect_browser_path(args.browser)
    if not browser_path:
        raise RuntimeError(f"Could not determine {args.browser.title()} path. Pass --browser-path.")

    user_data_dir = args.user_data_dir or tempfile.mkdtemp(prefix="cookie-monster-e2e-")
    proc = launch_browser(
        browser=args.browser,
        browser_path=browser_path,
        host=args.host,
        port=args.port,
        user_data_dir=user_data_dir,
        profile_directory=None,
        open_url=args.target_url,
        headless=args.headless,
    )
    try:
        wait_for_debug_endpoint(args.host, args.port)
        print(f"{args.browser.title()} DevTools is live. Generating capture...")

        captures = capture_requests(
            CaptureConfig(
                chrome_host=args.host,
                chrome_port=args.port,
                duration_seconds=args.duration,
                target_hint=args.target_hint,
                output_file=args.capture_file,
                include_all_headers=args.include_all_headers,
            )
        )
        print(f"Captured {len(captures)} request(s) to {args.capture_file}")

        if not captures:
            print("No captures found. Refresh the target site in the launched browser and rerun.")
            return

        response = replay_with_capture(
            ReplayConfig(
                capture_file=args.capture_file,
                request_url=args.replay_url,
                method="GET",
                url_contains=args.url_contains,
                output_file=args.response_file,
            )
        )
        print(f"Replay status: {response.status_code}")
        print(f"Response saved to {args.response_file}")

    finally:
        if not args.keep_open:
            proc.terminate()


if __name__ == "__main__":
    main()
