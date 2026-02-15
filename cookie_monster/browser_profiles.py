from __future__ import annotations

import json
import os
import platform
from pathlib import Path


def default_user_data_dir(browser: str) -> str | None:
    browser = browser.lower()
    system = platform.system().lower()
    home = str(Path.home())
    if "darwin" in system:
        roots = {
            "chrome": f"{home}/Library/Application Support/Google/Chrome",
            "edge": f"{home}/Library/Application Support/Microsoft Edge",
        }
        path = roots.get(browser)
        return path if path and Path(path).exists() else None
    if "windows" in system:
        local = os.path.expandvars(r"%LocalAppData%")
        roots = {
            "chrome": f"{local}\\Google\\Chrome\\User Data",
            "edge": f"{local}\\Microsoft\\Edge\\User Data",
        }
        path = roots.get(browser)
        return path if path and Path(path).exists() else None
    return None


def list_profiles(user_data_dir: str) -> list[dict[str, str]]:
    local_state = Path(user_data_dir) / "Local State"
    if not local_state.exists():
        raise FileNotFoundError(f"Local State not found in {user_data_dir}")

    data = json.loads(local_state.read_text(encoding="utf-8"))
    info_cache = data.get("profile", {}).get("info_cache", {})
    profiles: list[dict[str, str]] = []
    for profile_dir, details in info_cache.items():
        profiles.append(
            {
                "profile_directory": str(profile_dir),
                "name": str(details.get("name", "")),
                "email": str(details.get("user_name") or details.get("gaia_name") or ""),
            }
        )
    return sorted(profiles, key=lambda p: p["profile_directory"])
