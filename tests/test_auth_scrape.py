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


# ── _audience_domain ─────────────────────────────────────────────────────────


def test_audience_domain_extracts_netloc():
    assert ast._audience_domain("https://api.github.com/graphql") == "api.github.com"
    assert ast._audience_domain("http://localhost:8080/api") == "localhost:8080"


def test_audience_domain_handles_bare_string():
    assert ast._audience_domain("not-a-url") == "not-a-url"


def test_audience_domain_handles_empty():
    result = ast._audience_domain("")
    assert isinstance(result, str)


# ── _extract_token_details ───────────────────────────────────────────────────


def test_extract_token_details_multiple_requests():
    """Headers from different requests should each produce a detail entry."""
    captures = [
        {
            "url": "https://github.com/",
            "method": "GET",
            "headers": {"Cookie": "session=abc", "Authorization": "Bearer tok1"},
        },
        {
            "url": "https://api.github.com/graphql",
            "method": "POST",
            "headers": {"Cookie": "session=abc", "Authorization": "Bearer tok2"},
        },
    ]
    details = ast._extract_token_details(captures, ["cookie", "authorization"])
    assert len(details) >= 3  # at least 3 unique (header, value, domain)

    # Both domains should appear.
    domains = {d["audience_domain"] for d in details}
    assert "github.com" in domains
    assert "api.github.com" in domains

    # Every entry should have all required keys.
    for d in details:
        assert "header" in d
        assert "value" in d
        assert "audience_url" in d
        assert "audience_domain" in d
        assert "method" in d


def test_extract_token_details_deduplicates_same_value_same_domain():
    """Same header+value+domain should be collapsed to one entry."""
    captures = [
        {
            "url": "https://github.com/page1",
            "method": "GET",
            "headers": {"Cookie": "session=abc"},
        },
        {
            "url": "https://github.com/page2",
            "method": "GET",
            "headers": {"Cookie": "session=abc"},
        },
    ]
    details = ast._extract_token_details(captures, ["cookie"])
    cookie_details = [d for d in details if d["header"] == "cookie"]
    # Both requests go to github.com with the same cookie value → 1 entry.
    assert len(cookie_details) == 1
    assert cookie_details[0]["audience_domain"] == "github.com"


def test_extract_token_details_different_values_same_domain():
    """Different values for the same header on the same domain should NOT be deduped."""
    captures = [
        {
            "url": "https://api.example.com/a",
            "method": "GET",
            "headers": {"Authorization": "Bearer token-A"},
        },
        {
            "url": "https://api.example.com/b",
            "method": "POST",
            "headers": {"Authorization": "Bearer token-B"},
        },
    ]
    details = ast._extract_token_details(captures, ["authorization"])
    assert len(details) == 2
    values = {d["value"] for d in details}
    assert "Bearer token-A" in values
    assert "Bearer token-B" in values


def test_extract_token_details_empty_captures():
    details = ast._extract_token_details([], ["cookie"])
    assert details == []


def test_extract_token_details_ignores_non_requested_headers():
    captures = [
        {
            "url": "https://example.com/",
            "method": "GET",
            "headers": {"Cookie": "a=1", "X-Request-Id": "abc123"},
        },
    ]
    details = ast._extract_token_details(captures, ["cookie"])
    assert len(details) == 1
    assert details[0]["header"] == "cookie"


def test_extract_token_details_case_insensitive():
    captures = [
        {
            "url": "https://example.com/",
            "method": "GET",
            "headers": {"AUTHORIZATION": "Bearer UP", "cookie": "low=1"},
        },
    ]
    details = ast._extract_token_details(captures, ["Cookie", "Authorization"])
    headers = {d["header"] for d in details}
    assert "cookie" in headers
    assert "authorization" in headers


def test_extract_token_details_preserves_method():
    captures = [
        {
            "url": "https://api.example.com/data",
            "method": "POST",
            "headers": {"Authorization": "Bearer x"},
        },
    ]
    details = ast._extract_token_details(captures, ["authorization"])
    assert details[0]["method"] == "POST"


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
