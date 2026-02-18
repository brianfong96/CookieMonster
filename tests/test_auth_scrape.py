"""Tests for scripts/auth_scrape_tabs.py.

These are pure unit tests — no browser or network access required.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

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


# ── _extract_tokens ──────────────────────────────────────────────────────────


def test_extract_tokens_finds_matching_headers():
    captures = [
        {"headers": {"X-Request-Id": "abc"}},
        {"headers": {"Cookie": "session=xyz", "Authorization": "Bearer tok123"}},
        {"headers": {"Cookie": "ignored"}},
    ]
    tokens = ast._extract_tokens(captures, ["cookie", "authorization"])
    assert tokens["cookie"] == "session=xyz"
    assert tokens["authorization"] == "Bearer tok123"


def test_extract_tokens_returns_none_for_missing():
    captures = [{"headers": {"Cookie": "a=1"}}]
    tokens = ast._extract_tokens(captures, ["cookie", "authorization", "x-csrf-token"])
    assert tokens["cookie"] == "a=1"
    assert tokens["authorization"] is None
    assert tokens["x-csrf-token"] is None


def test_extract_tokens_case_insensitive():
    captures = [{"headers": {"COOKIE": "upper=1", "authorization": "lower"}}]
    tokens = ast._extract_tokens(captures, ["Cookie", "Authorization"])
    assert tokens["cookie"] == "upper=1"
    assert tokens["authorization"] == "lower"


def test_extract_tokens_empty_captures():
    tokens = ast._extract_tokens([], ["cookie"])
    assert tokens == {"cookie": None}


# ── _resolve_profile ─────────────────────────────────────────────────────────


def test_resolve_profile_by_email(monkeypatch):
    """Matching on email should set profile_directory."""
    cfg = ast.ScrapeConfig(email="user@example.com", browser="chrome")

    monkeypatch.setattr(
        ast, "default_user_data_dir",
        lambda browser: "/fake/chrome/data",
    )
    monkeypatch.setattr(
        ast, "list_profiles",
        lambda data_dir: [
            {"profile_directory": "Profile 1", "name": "Work", "email": "user@example.com"},
            {"profile_directory": "Default", "name": "Personal", "email": "other@example.com"},
        ],
    )

    ast._resolve_profile(cfg)
    assert cfg.profile_directory == "Profile 1"
    assert cfg.user_data_dir == "/fake/chrome/data"


def test_resolve_profile_by_name(monkeypatch):
    """When email field is empty, fall back to matching by display name."""
    cfg = ast.ScrapeConfig(email="Brian", browser="chrome")

    monkeypatch.setattr(
        ast, "default_user_data_dir",
        lambda browser: "/fake/chrome/data",
    )
    monkeypatch.setattr(
        ast, "list_profiles",
        lambda data_dir: [
            {"profile_directory": "Default", "name": "Brian", "email": ""},
            {"profile_directory": "Profile 1", "name": "Work", "email": "work@co.com"},
        ],
    )

    ast._resolve_profile(cfg)
    assert cfg.profile_directory == "Default"


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


def test_resolve_profile_raises_on_no_match(monkeypatch):
    cfg = ast.ScrapeConfig(email="unknown@nowhere.com", browser="chrome")

    monkeypatch.setattr(
        ast, "default_user_data_dir",
        lambda browser: "/fake/chrome/data",
    )
    monkeypatch.setattr(
        ast, "list_profiles",
        lambda data_dir: [
            {"profile_directory": "Default", "name": "Brian", "email": "brian@x.com"},
        ],
    )

    with pytest.raises(RuntimeError, match="No chrome profile found"):
        ast._resolve_profile(cfg)


# ── _browser_is_reachable ────────────────────────────────────────────────────


def test_browser_is_reachable_true(monkeypatch):
    class FakeResp:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda url, timeout=1: FakeResp(),
    )
    assert ast._browser_is_reachable("127.0.0.1", 9222) is True


def test_browser_is_reachable_false(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda url, timeout=1: (_ for _ in ()).throw(ConnectionError("nope")),
    )
    assert ast._browser_is_reachable("127.0.0.1", 9222) is False


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
