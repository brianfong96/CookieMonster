"""Tests for scripts/auth_scrape_tabs.py.

These are pure unit tests — no browser or network access required.
Tests for the library helpers that were moved out of the script
(extract_tokens, extract_token_details, audience_domain, resolve_profile,
browser_is_reachable, is_browser_process_running) now live in their
respective library test files:
  - tests/test_capture_extract.py
  - tests/test_browser_profiles.py
  - tests/test_launcher.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure the scripts directory is on sys.path so we can import the module.
_scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import auth_scrape_tabs as ast  # noqa: E402

# ── load_config ───────────────────────────────────────────────────────────────


def test_load_config_parses_sample(tmp_path: Path):
    cfg_data = {
        "browser": "edge",
        "port": 9333,
        "email": "user@example.com",
        "capture_duration_seconds": 5,
        "output_file": "out.json",
        "targets": [
            {"name": "Site A", "url": "https://a.example.com", "hint": "a.example.com"},
            {"url": "https://b.example.com", "extract": ["authorization"]},
        ],
    }
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(cfg_data))

    cfg = ast.load_config(str(cfg_path))

    assert cfg.browser == "edge"
    assert cfg.port == 9333
    assert cfg.email == "user@example.com"
    assert cfg.capture_duration_seconds == 5
    assert len(cfg.targets) == 2
    assert cfg.targets[0].name == "Site A"
    assert cfg.targets[0].hint == "a.example.com"
    assert cfg.targets[0].extract == ["cookie", "authorization"]  # default
    assert cfg.targets[1].name == "https://b.example.com"  # falls back to url
    assert cfg.targets[1].extract == ["authorization"]


def test_load_config_defaults(tmp_path: Path):
    """A minimal config with just targets should use all defaults."""
    cfg_path = tmp_path / "min.json"
    cfg_path.write_text(json.dumps({"targets": [{"url": "https://x.com"}]}))

    cfg = ast.load_config(str(cfg_path))

    assert cfg.browser == "chrome"
    assert cfg.port == 9222
    assert cfg.headless is False
    assert cfg.email is None
    assert cfg.profile_directory is None
    assert len(cfg.targets) == 1


# ── _resolve_profile (thin wrapper) ──────────────────────────────────────────


def test_resolve_profile_delegates_to_library(monkeypatch):
    """The script wrapper should call the library's resolve_profile."""
    cfg = ast.ScrapeConfig(email="user@example.com", browser="chrome")

    monkeypatch.setattr(
        ast, "resolve_profile",
        lambda email, browser, user_data_dir: ("/fake/data", "Profile 1"),
    )

    ast._resolve_profile(cfg)
    assert cfg.profile_directory == "Profile 1"
    assert cfg.user_data_dir == "/fake/data"


def test_resolve_profile_skips_when_already_set():
    """If profile_directory is already set, _resolve_profile should be a no-op."""
    cfg = ast.ScrapeConfig(email="user@example.com", profile_directory="Default")
    ast._resolve_profile(cfg)
    assert cfg.profile_directory == "Default"


def test_resolve_profile_skips_when_no_email():
    """If no email is provided, _resolve_profile should be a no-op."""
    cfg = ast.ScrapeConfig()
    ast._resolve_profile(cfg)
    assert cfg.profile_directory is None


# ── TargetSpec / ScrapeConfig defaults ────────────────────────────────────────


def test_target_spec_defaults():
    t = ast.TargetSpec(name="Test", url="https://example.com")
    assert t.extract == ["cookie", "authorization"]
    assert t.hint is None


def test_scrape_config_defaults():
    cfg = ast.ScrapeConfig()
    assert cfg.browser == "chrome"
    assert cfg.port == 9222
    assert cfg.headless is False
    assert cfg.output_file == "auth_scrape_results.json"
    assert "cookie" in cfg.header_allowlist
    assert "authorization" in cfg.header_allowlist


# ── build_parser ──────────────────────────────────────────────────────────────


def test_build_parser_accepts_config_flag():
    parser = ast.build_parser()
    args = parser.parse_args(["--config", "test.json", "-v"])
    assert args.config == "test.json"
    assert args.verbose is True


def test_build_parser_accepts_url_flags():
    parser = ast.build_parser()
    args = parser.parse_args(["-u", "https://a.com", "--url", "https://b.com"])
    assert args.url == ["https://a.com", "https://b.com"]


def test_build_parser_accepts_all_overrides():
    parser = ast.build_parser()
    args = parser.parse_args([
        "--browser", "edge",
        "--port", "9333",
        "--email", "me@co.com",
        "--headless",
        "--capture-duration", "20",
        "--settle-delay", "5",
        "--output", "out.json",
        "--include-all-headers",
        "--keep-open",
        "-u", "https://x.com",
    ])
    assert args.browser == "edge"
    assert args.port == 9333
    assert args.email == "me@co.com"
    assert args.headless is True
    assert args.capture_duration_seconds == 20.0
    assert args.settle_delay_seconds == 5.0
    assert args.output_file == "out.json"
    assert args.include_all_headers is True
    assert args.keep_open is True


# ── sample config file valid JSON ─────────────────────────────────────────────


def test_sample_config_is_valid_json():
    sample = Path(__file__).resolve().parent.parent / "scripts" / "auth_scrape_config.sample.json"
    data = json.loads(sample.read_text())
    assert "targets" in data
    assert isinstance(data["targets"], list)
    assert len(data["targets"]) > 0
