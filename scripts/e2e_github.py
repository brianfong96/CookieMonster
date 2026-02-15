from __future__ import annotations

import argparse
import os
import platform
import subprocess
import tempfile
import time
import urllib.request

from cookie_monster.capture import capture_requests
from cookie_monster.config import CaptureConfig, ReplayConfig
from cookie_monster.replay import replay_with_capture


def _default_chrome_path() -> str | None:
    system = platform.system().lower()
    if "darwin" in system:
        path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        return path if os.path.exists(path) else None
    if "windows" in system:
        candidates = [
            os.path.expandvars(r"%ProgramFiles%\\Google\\Chrome\\Application\\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\\Google\\Chrome\\Application\\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\\Google\\Chrome\\Application\\chrome.exe"),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
    return None


def _wait_for_debug_endpoint(host: str, port: int, timeout_seconds: int = 15) -> None:
    deadline = time.time() + timeout_seconds
    url = f"http://{host}:{port}/json/version"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    raise RuntimeError(f"Chrome DevTools endpoint did not come up at {url}")


def main() -> None:
    parser = argparse.ArgumentParser(description="E2E smoke test with Chrome + target site")
    parser.add_argument("--chrome-path", default=_default_chrome_path())
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

    if not args.chrome_path:
        raise RuntimeError("Could not determine Chrome path. Pass --chrome-path.")

    user_data_dir = args.user_data_dir or tempfile.mkdtemp(prefix="cookie-monster-e2e-")
    chrome_args = [
        args.chrome_path,
        f"--remote-debugging-port={args.port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={user_data_dir}",
        "--new-window",
        args.target_url,
    ]
    if args.headless:
        chrome_args.insert(1, "--headless=new")

    proc = subprocess.Popen(chrome_args)
    try:
        _wait_for_debug_endpoint(args.host, args.port)
        print("Chrome DevTools is live. Generating capture...")

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
            print("No captures found. Refresh GitHub in the launched Chrome window and rerun.")
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
