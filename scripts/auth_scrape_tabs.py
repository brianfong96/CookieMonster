#!/usr/bin/env python3
"""Batch auth-token / cookie scraper using a single browser session with tabs.

Opens one browser, creates a tab per target URL from a JSON config file,
captures cookies and auth headers from network traffic, then writes a
consolidated results file.  The browser stays open for the entire run so
you only pay the startup cost once.

Usage::

    # With a config file
    python scripts/auth_scrape_tabs.py --config scripts/auth_scrape_config.sample.json

    # Override individual settings
    python scripts/auth_scrape_tabs.py --config my_config.json --headless --port 9223

    # Minimal inline usage (no config file)
    python scripts/auth_scrape_tabs.py \
        --url https://github.com/ \
        --url https://github.com/settings/profile \
        --extract cookie authorization
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Allow running from the repo root or the scripts/ directory.
_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from cookie_monster.browser_profiles import default_user_data_dir, list_profiles
from cookie_monster.cdp import CDPClient
from cookie_monster.chrome_discovery import get_websocket_debug_url, list_page_targets
from cookie_monster.chrome_launcher import (
    detect_browser_path,
    launch_browser,
    wait_for_debug_endpoint,
)
from cookie_monster.tab_manager import TabHandle, TabManager, TabManagerConfig

logger = logging.getLogger("auth_scrape_tabs")

# ── data types ────────────────────────────────────────────────────────────────


@dataclass
class TargetSpec:
    """One URL to visit and scrape."""

    name: str
    url: str
    hint: str | None = None
    extract: list[str] = field(default_factory=lambda: ["cookie", "authorization"])


@dataclass
class ScrapeConfig:
    """Top-level configuration loaded from JSON (+ CLI overrides)."""

    browser: str = "chrome"
    browser_path: str | None = None
    host: str = "127.0.0.1"
    port: int = 9222
    headless: bool = False
    user_data_dir: str | None = None
    profile_directory: str | None = None
    email: str | None = None
    load_timeout_seconds: float = 30.0
    capture_duration_seconds: float = 10.0
    settle_delay_seconds: float = 3.0
    output_file: str = "auth_scrape_results.json"
    include_all_headers: bool = False
    header_allowlist: list[str] = field(
        default_factory=lambda: [
            "cookie",
            "authorization",
            "x-csrf-token",
            "x-xsrf-token",
            "set-cookie",
        ]
    )
    targets: list[TargetSpec] = field(default_factory=list)


def load_config(path: str) -> ScrapeConfig:
    """Load a :class:`ScrapeConfig` from a JSON file."""
    with open(path, "r", encoding="utf-8") as fh:
        raw: dict[str, Any] = json.load(fh)

    targets = [
        TargetSpec(
            name=str(t.get("name", t.get("url", ""))),
            url=str(t["url"]),
            hint=t.get("hint"),
            extract=list(t.get("extract", ["cookie", "authorization"])),
        )
        for t in raw.pop("targets", [])
    ]
    cfg = ScrapeConfig(**{k: v for k, v in raw.items() if k in ScrapeConfig.__dataclass_fields__})
    cfg.targets = targets
    return cfg


# ── network capture per tab ───────────────────────────────────────────────────


def _connect_and_enable_network(
    host: str, port: int, target_id: str,
) -> CDPClient:
    """Connect a CDP client to *target_id* and enable the Network domain.

    The caller is responsible for calling ``client.close()``.
    """
    ws_url = f"ws://{host}:{port}/devtools/page/{target_id}"
    client = CDPClient(ws_url)
    client.connect()
    client.send_command("Network.enable", {})
    return client


def _read_network_events(
    client: CDPClient,
    duration: float,
    allowlist: list[str],
    include_all: bool,
) -> list[dict[str, Any]]:
    """Read network events from an already-connected CDP client.

    Returns a list of dicts with ``url``, ``method``, and ``headers`` keys.
    """
    captured: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    request_state: dict[str, dict[str, Any]] = {}
    allowed = {h.lower() for h in allowlist}

    try:
        deadline = time.time() + duration

        while time.time() < deadline:
            event = client.read_event(timeout_seconds=1.0)
            if event is None:
                continue

            method = str(event.get("method", ""))
            params = dict(event.get("params", {}))

            if method == "Network.requestWillBeSent":
                req_id = str(params.get("requestId", ""))
                request = dict(params.get("request", {}))
                state = request_state.setdefault(req_id, {})
                state["url"] = str(request.get("url", ""))
                state["method"] = str(request.get("method", "GET"))
                raw_headers = {str(k): str(v) for k, v in dict(request.get("headers", {})).items()}
                state.setdefault("headers", {}).update(raw_headers)

            elif method == "Network.requestWillBeSentExtraInfo":
                req_id = str(params.get("requestId", ""))
                state = request_state.setdefault(req_id, {})
                extra = {str(k): str(v) for k, v in dict(params.get("headers", {})).items()}
                state.setdefault("headers", {}).update(extra)

            elif method == "Network.responseReceived":
                resp = dict(params.get("response", {}))
                resp_headers = {str(k): str(v) for k, v in dict(resp.get("headers", {})).items()}
                req_id = str(params.get("requestId", ""))
                state = request_state.setdefault(req_id, {})
                state.setdefault("response_headers", {}).update(resp_headers)

            # Emit captured entries as they become available
            for req_id, state in list(request_state.items()):
                if req_id in seen_ids:
                    continue
                all_hdrs = dict(state.get("headers", {}))
                resp_hdrs = dict(state.get("response_headers", {}))
                all_hdrs.update(resp_hdrs)
                if not all_hdrs:
                    continue

                if include_all:
                    filtered = all_hdrs
                else:
                    filtered = {k: v for k, v in all_hdrs.items() if k.lower() in allowed}
                if not filtered:
                    continue

                captured.append(
                    {
                        "url": state.get("url", ""),
                        "method": state.get("method", "GET"),
                        "headers": filtered,
                    }
                )
                seen_ids.add(req_id)
    finally:
        try:
            client.send_command("Network.disable", {})
        except Exception:
            pass
        client.close()

    return captured


# ── extract helpers ───────────────────────────────────────────────────────────


def _extract_tokens(
    captures: list[dict[str, Any]],
    extract_keys: list[str],
) -> dict[str, str | None]:
    """Pull the first occurrence of each requested header from captured traffic."""
    result: dict[str, str | None] = {k.lower(): None for k in extract_keys}
    for entry in captures:
        headers = entry.get("headers", {})
        for key in extract_keys:
            low = key.lower()
            if result.get(low) is not None:
                continue
            for hk, hv in headers.items():
                if hk.lower() == low:
                    result[low] = hv
                    break
        if all(v is not None for v in result.values()):
            break
    return result


# ── profile resolution ────────────────────────────────────────────────────────


def _resolve_profile(cfg: ScrapeConfig) -> None:
    """If *email* is set but *profile_directory* is not, enumerate Chrome/Edge
    profiles and resolve the matching profile directory in-place.
    """
    if not cfg.email or cfg.profile_directory:
        return  # nothing to resolve

    data_dir = cfg.user_data_dir or default_user_data_dir(cfg.browser)
    if not data_dir:
        raise RuntimeError(
            f"Cannot auto-detect profile: no user_data_dir and could not find "
            f"the default {cfg.browser} data directory."
        )

    # Persist the resolved data dir so launch_browser uses the real profile root.
    cfg.user_data_dir = data_dir

    profiles = list_profiles(data_dir)
    needle = cfg.email.strip().lower()
    for p in profiles:
        # Match on email first, then fall back to profile display name.
        if (
            (p["email"] and p["email"].lower() == needle)
            or p["name"].lower() == needle
        ):
            cfg.profile_directory = p["profile_directory"]
            logger.info(
                "Resolved '%s' → profile '%s' (%s)",
                cfg.email,
                p["name"],
                p["profile_directory"],
            )
            return

    available = ", ".join(
        f"{p['name']} / {p['email']} ({p['profile_directory']})" for p in profiles
    )
    raise RuntimeError(
        f"No {cfg.browser} profile found for '{cfg.email}'. "
        f"Available profiles: {available}"
    )


# ── browser lifecycle (idempotent) ────────────────────────────────────────────


def _browser_is_reachable(host: str, port: int) -> bool:
    """Return ``True`` if a DevTools endpoint is already listening."""
    import urllib.request

    url = f"http://{host}:{port}/json/version"
    try:
        with urllib.request.urlopen(url, timeout=5):
            return True
    except Exception:  # noqa: BLE001
        return False


def _is_browser_process_running(browser: str) -> bool:
    """Return ``True`` if any process matching *browser* is running."""
    import platform
    import subprocess

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


# ── main orchestration ────────────────────────────────────────────────────────


def run_scrape(cfg: ScrapeConfig) -> list[dict[str, Any]]:
    """Idempotent scrape: reuse an already-running browser or launch one.

    If a browser is already listening on ``cfg.host:cfg.port``, the script
    attaches to it, opens/refreshes tabs, captures traffic, and leaves the
    browser running.  If no browser is found it launches one, and only
    terminates it afterwards when ``keep_browser`` is ``False``.
    """

    # ── resolve email → profile_directory ──
    _resolve_profile(cfg)

    browser_path = cfg.browser_path or detect_browser_path(cfg.browser)
    if not browser_path:
        raise RuntimeError(
            f"Could not find {cfg.browser}. Pass browser_path in the config or install the browser."
        )

    # ── idempotent browser start ──
    already_running = _browser_is_reachable(cfg.host, cfg.port)
    proc = None  # only set when *we* launched the browser

    if already_running:
        logger.info(
            "Browser already running at %s:%s – reusing existing session.",
            cfg.host,
            cfg.port,
        )
    else:
        # Check if the browser is running *without* a debug port.
        if _is_browser_process_running(cfg.browser):
            logger.warning(
                "%s is running but NOT with --remote-debugging-port=%d. "
                "Please close all %s windows first, or start %s manually with: "
                "%s --remote-debugging-port=%d --remote-allow-origins=*",
                cfg.browser.title(),
                cfg.port,
                cfg.browser.title(),
                cfg.browser.title(),
                browser_path,
                cfg.port,
            )
            raise RuntimeError(
                f"{cfg.browser.title()} is already running without a debug port. "
                f"Close all {cfg.browser.title()} windows and retry, or start it "
                f"manually with --remote-debugging-port={cfg.port}."
            )

        logger.info("No browser detected – launching %s…", cfg.browser)
        user_data_dir = cfg.user_data_dir or tempfile.mkdtemp(prefix="cookie-monster-scrape-")
        first_url = cfg.targets[0].url if cfg.targets else "about:blank"
        proc = launch_browser(
            browser=cfg.browser,
            browser_path=browser_path,
            host=cfg.host,
            port=cfg.port,
            user_data_dir=user_data_dir,
            profile_directory=cfg.profile_directory,
            open_url=first_url,
            headless=cfg.headless,
        )
        wait_for_debug_endpoint(cfg.host, cfg.port, timeout_seconds=60)
        logger.info("Browser DevTools ready at %s:%s", cfg.host, cfg.port)

    results: list[dict[str, Any]] = []

    try:
        mgr_cfg = TabManagerConfig(
            chrome_host=cfg.host,
            chrome_port=cfg.port,
            load_timeout_seconds=cfg.load_timeout_seconds,
        )

        with TabManager(mgr_cfg) as mgr:
            existing_tabs = mgr.list_tabs()

            # Build URL → existing tab lookup so we can reuse tabs that
            # already have the right URL instead of opening duplicates.
            url_to_tab: dict[str, TabHandle] = {}
            for tab in existing_tabs:
                url_to_tab.setdefault(tab.url.rstrip("/"), tab)

            tab_map: dict[str, tuple[TargetSpec, TabHandle]] = {}
            tabs_we_opened: list[str] = []  # target_ids we created (for cleanup)

            for idx, spec in enumerate(cfg.targets, start=1):
                normalised = spec.url.rstrip("/")
                existing = url_to_tab.get(normalised)
                if existing:
                    tab_map[existing.target_id] = (spec, existing)
                    logger.info(
                        "[%d/%d] Reusing existing tab for %s (%s)",
                        idx,
                        len(cfg.targets),
                        spec.name,
                        spec.url,
                    )
                else:
                    handle = mgr.open_tab(spec.url)
                    tab_map[handle.target_id] = (spec, handle)
                    tabs_we_opened.append(handle.target_id)
                    logger.info(
                        "[%d/%d] Opened new tab for %s (%s)",
                        idx,
                        len(cfg.targets),
                        spec.name,
                        spec.url,
                    )

            # Give pages time to settle (XHR, redirects, SPAs, etc.)
            settle = max(0.0, cfg.settle_delay_seconds)
            if settle:
                logger.info("Waiting %.1fs for pages to settle…", settle)
                time.sleep(settle)

            # Capture network traffic from each tab.
            #
            # IMPORTANT: We must enable Network.enable BEFORE refreshing
            # the page, otherwise all request events fire and complete
            # before our listener is attached, resulting in 0 captures.
            for target_id, (spec, handle) in tab_map.items():
                logger.info("Capturing traffic for %s (%s)…", spec.name, spec.url)

                # 1. Connect to the tab and start listening for network events.
                cdp_client = _connect_and_enable_network(
                    host=cfg.host,
                    port=cfg.port,
                    target_id=target_id,
                )

                # 2. Now trigger the page load so events flow into 
                #    the listener we just set up.
                if handle.url.rstrip("/") != spec.url.rstrip("/"):
                    mgr.navigate(target_id, spec.url)
                else:
                    mgr.refresh(target_id, ignore_cache=True)

                # 3. Read the events that fire from the refresh.
                raw_captures = _read_network_events(
                    client=cdp_client,
                    duration=cfg.capture_duration_seconds,
                    allowlist=cfg.header_allowlist,
                    include_all=cfg.include_all_headers,
                )

                tokens = _extract_tokens(raw_captures, spec.extract)

                entry: dict[str, Any] = {
                    "name": spec.name,
                    "url": spec.url,
                    "tokens": tokens,
                    "raw_capture_count": len(raw_captures),
                }
                results.append(entry)

                found = sum(1 for v in tokens.values() if v is not None)
                logger.info(
                    "  → %d/%d tokens found, %d raw captures",
                    found,
                    len(tokens),
                    len(raw_captures),
                )

            # Only close tabs we opened (leave pre-existing ones alone).
            for tid in tabs_we_opened:
                mgr.close_tab(tid)

    finally:
        # Only terminate the browser if *we* launched it.
        if proc is not None:
            proc.terminate()
            logger.info("Browser terminated (launched by this script).")
        else:
            logger.info("Leaving pre-existing browser running.")

    return results


# ── CLI ───────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Batch auth-token / cookie scraper (single browser, multiple tabs).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  # Use a config file
  python scripts/auth_scrape_tabs.py --config scripts/auth_scrape_config.sample.json

  # Quick inline run
  python scripts/auth_scrape_tabs.py --url https://github.com/ --url https://example.com/

  # Headless with custom port
  python scripts/auth_scrape_tabs.py --config my.json --headless --port 9223
""",
    )
    p.add_argument(
        "--config", "-c",
        metavar="JSON",
        help="Path to a JSON config file (see auth_scrape_config.sample.json).",
    )
    p.add_argument("--url", "-u", action="append", default=[], help="Target URL(s) to scrape. Repeatable.")
    p.add_argument("--extract", "-e", nargs="+", default=None, help="Header names to extract (default: cookie authorization).")
    p.add_argument("--browser", default=None, choices=["chrome", "edge"])
    p.add_argument("--browser-path", default=None)
    p.add_argument("--host", default=None)
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--headless", action="store_true", default=None)
    p.add_argument("--user-data-dir", default=None)
    p.add_argument("--profile-directory", default=None)
    p.add_argument("--email", default=None, help="Google account email – auto-detects the Chrome/Edge profile directory.")
    p.add_argument("--load-timeout", type=float, default=None, dest="load_timeout_seconds")
    p.add_argument("--capture-duration", type=float, default=None, dest="capture_duration_seconds")
    p.add_argument("--settle-delay", type=float, default=None, dest="settle_delay_seconds")
    p.add_argument("--output", "-o", default=None, dest="output_file")
    p.add_argument("--include-all-headers", action="store_true", default=None)
    p.add_argument("--keep-open", action="store_true", help="Keep the browser open after scraping (for debugging).")
    p.add_argument("--verbose", "-v", action="store_true")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Start from config file or defaults.
    if args.config:
        cfg = load_config(args.config)
        logger.info("Loaded config from %s (%d targets)", args.config, len(cfg.targets))
    else:
        cfg = ScrapeConfig()

    # CLI overrides.
    for attr in (
        "browser", "browser_path", "host", "port", "headless",
        "user_data_dir", "profile_directory", "email",
        "load_timeout_seconds",
        "capture_duration_seconds", "settle_delay_seconds", "output_file",
        "include_all_headers",
    ):
        val = getattr(args, attr, None)
        if val is not None:
            setattr(cfg, attr, val)

    # --url flags add extra targets (or replace empty list from no-config mode).
    default_extract = args.extract or ["cookie", "authorization"]
    for url in args.url:
        cfg.targets.append(TargetSpec(name=url, url=url, extract=default_extract))

    if not cfg.targets:
        parser.error("Provide targets via --config or --url.")

    # Execute the scrape.
    results = run_scrape(cfg)

    # Ensure output directory exists.
    out_path = cfg.output_file
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print(f"\nResults written to {out_path}")
    print(f"{'─' * 60}")
    for entry in results:
        found = sum(1 for v in entry["tokens"].values() if v is not None)
        total = len(entry["tokens"])
        status = "✓" if found == total else ("◐" if found else "✗")
        print(f"  {status} {entry['name']}: {found}/{total} tokens captured")
        for key, val in entry["tokens"].items():
            preview = (val[:80] + "…") if val and len(val) > 80 else val
            print(f"      {key}: {preview}")
    print()


if __name__ == "__main__":
    main()
