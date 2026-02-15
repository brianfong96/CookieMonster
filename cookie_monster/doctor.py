from __future__ import annotations

import urllib.request
from pathlib import Path

from .browser_profiles import default_user_data_dir
from .chrome_discovery import list_targets
from .chrome_launcher import detect_browser_path


def run_doctor(browser: str, host: str, port: int, user_data_dir: str | None = None) -> dict:
    report = {
        "browser": browser,
        "browser_path": None,
        "browser_path_exists": False,
        "user_data_dir": None,
        "user_data_dir_exists": False,
        "devtools_endpoint": f"http://{host}:{port}",
        "devtools_reachable": False,
        "target_count": 0,
        "errors": [],
    }

    try:
        bpath = detect_browser_path(browser)
        report["browser_path"] = bpath
        report["browser_path_exists"] = bool(bpath)
        if not bpath:
            report["errors"].append("Browser executable not found")
    except Exception as exc:  # noqa: BLE001
        report["errors"].append(f"Browser path detection failed: {exc}")

    udir = user_data_dir or default_user_data_dir(browser)
    report["user_data_dir"] = udir
    report["user_data_dir_exists"] = bool(udir and Path(udir).exists())
    if not report["user_data_dir_exists"]:
        report["errors"].append("User data directory not found")

    try:
        with urllib.request.urlopen(f"http://{host}:{port}/json/version", timeout=2):
            report["devtools_reachable"] = True
        targets = list_targets(host, port, retries=1)
        report["target_count"] = len(targets)
    except Exception as exc:  # noqa: BLE001
        report["errors"].append(f"DevTools not reachable: {exc}")

    return report
