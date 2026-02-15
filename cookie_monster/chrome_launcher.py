from __future__ import annotations

import os
import platform
import subprocess
import tempfile
import time
import urllib.request


def detect_browser_path(browser: str) -> str | None:
    browser = browser.lower()
    if browser not in {"chrome", "edge"}:
        raise ValueError(f"Unsupported browser: {browser}")

    system = platform.system().lower()
    if "darwin" in system:
        app_paths = {
            "chrome": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "edge": "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        }
        path = app_paths[browser]
        return path if os.path.exists(path) else None
    if "windows" in system:
        candidates = {
            "chrome": [
                os.path.expandvars(r"%ProgramFiles%\\Google\\Chrome\\Application\\chrome.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\\Google\\Chrome\\Application\\chrome.exe"),
                os.path.expandvars(r"%LocalAppData%\\Google\\Chrome\\Application\\chrome.exe"),
            ],
            "edge": [
                os.path.expandvars(r"%ProgramFiles%\\Microsoft\\Edge\\Application\\msedge.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\\Microsoft\\Edge\\Application\\msedge.exe"),
                os.path.expandvars(r"%LocalAppData%\\Microsoft\\Edge\\Application\\msedge.exe"),
            ],
        }[browser]
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
    return None


def wait_for_debug_endpoint(host: str, port: int, timeout_seconds: int = 15) -> None:
    deadline = time.time() + timeout_seconds
    url = f"http://{host}:{port}/json/version"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    raise RuntimeError(f"Chrome DevTools endpoint did not come up at {url}")


def launch_browser(
    browser: str,
    browser_path: str | None,
    host: str,
    port: int,
    user_data_dir: str | None,
    profile_directory: str | None,
    open_url: str | None,
    headless: bool,
) -> subprocess.Popen[bytes]:
    resolved = browser_path or detect_browser_path(browser)
    if not resolved:
        raise RuntimeError(
            f"Could not determine {browser.title()} path. "
            "Pass --browser-path (or --chrome-path for compatibility)."
        )

    profile_root = user_data_dir or tempfile.mkdtemp(prefix="cookie-monster-profile-")
    args: list[str] = [
        resolved,
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={profile_root}",
    ]

    if profile_directory:
        args.append(f"--profile-directory={profile_directory}")
    if headless:
        args.append("--headless=new")
    if open_url:
        args.extend(["--new-window", open_url])

    return subprocess.Popen(args)


def detect_chrome_path() -> str | None:
    return detect_browser_path("chrome")


def launch_chrome(
    chrome_path: str | None,
    host: str,
    port: int,
    user_data_dir: str | None,
    profile_directory: str | None,
    open_url: str | None,
    headless: bool,
) -> subprocess.Popen[bytes]:
    return launch_browser(
        browser="chrome",
        browser_path=chrome_path,
        host=host,
        port=port,
        user_data_dir=user_data_dir,
        profile_directory=profile_directory,
        open_url=open_url,
        headless=headless,
    )
