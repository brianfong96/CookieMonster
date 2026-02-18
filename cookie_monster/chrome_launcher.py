from __future__ import annotations

import ctypes
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


def browser_is_reachable(host: str, port: int) -> bool:
    """Return ``True`` if a DevTools endpoint is already listening."""
    url = f"http://{host}:{port}/json/version"
    try:
        with urllib.request.urlopen(url, timeout=5):
            return True
    except Exception:  # noqa: BLE001
        return False


def is_browser_process_running(browser: str) -> bool:
    """Return ``True`` if any process matching *browser* is running.

    On Windows this checks ``tasklist``; on POSIX it uses ``pgrep``.
    """
    name_map = {"chrome": "chrome", "edge": "msedge"}
    needle = name_map.get(browser.lower(), browser.lower())
    system = platform.system().lower()

    try:
        if "windows" in system:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {needle}.exe", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return needle.lower() in result.stdout.lower()
        else:
            result = subprocess.run(
                ["pgrep", "-if", needle],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
    except Exception:  # noqa: BLE001
        return False


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

    # On Windows, Chrome needs special handling for two reasons:
    # 1. Paths with spaces (e.g. "User Data") must use the Windows 8.3
    #    short path to avoid Chrome's CLI parser splitting the argument.
    # 2. Chrome must be launched in its own console (CREATE_NEW_CONSOLE)
    #    so the debug port binds reliably when spawned from Python.
    if platform.system().lower() == "windows":
        if "--enable-logging" not in args:
            args.append("--enable-logging")

        # Convert any path with spaces to the Windows 8.3 short form so
        # Chrome's command-line parser never sees embedded spaces.
        def _short_path(p: str) -> str:
            if " " not in p:
                return p
            buf = ctypes.create_unicode_buffer(260)
            n = ctypes.windll.kernel32.GetShortPathNameW(p, buf, 260)
            return buf.value if n else p  # fall back to original on error

        def _fix_arg(a: str) -> str:
            if "=" in a:
                flag, _, value = a.partition("=")
                return f"{flag}={_short_path(value)}"
            if " " in a and not a.startswith("-"):
                return _short_path(a)
            return a

        args = [_fix_arg(a) for a in args]

        return subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )  # type: ignore[return-value]

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
