"""Tests for cookie_monster.browser_profiles."""

from __future__ import annotations

import json

import pytest

from cookie_monster.browser_profiles import list_profiles, resolve_profile

# ── resolve_profile ──────────────────────────────────────────────────────────


def test_resolve_profile_by_email(monkeypatch, tmp_path):
    """Matching on email should return the correct profile directory."""
    local_state = tmp_path / "Local State"
    local_state.write_text(json.dumps({
        "profile": {
            "info_cache": {
                "Profile 1": {"name": "Work", "user_name": "user@example.com"},
                "Default": {"name": "Personal", "user_name": "other@example.com"},
            }
        }
    }))

    data_dir, profile_dir = resolve_profile(
        email="user@example.com",
        browser="chrome",
        user_data_dir=str(tmp_path),
    )
    assert profile_dir == "Profile 1"
    assert data_dir == str(tmp_path)


def test_resolve_profile_by_name(monkeypatch, tmp_path):
    """When email field is empty, fall back to matching by display name."""
    local_state = tmp_path / "Local State"
    local_state.write_text(json.dumps({
        "profile": {
            "info_cache": {
                "Default": {"name": "Brian", "user_name": ""},
                "Profile 1": {"name": "Work", "user_name": "work@co.com"},
            }
        }
    }))

    data_dir, profile_dir = resolve_profile(
        email="Brian",
        browser="chrome",
        user_data_dir=str(tmp_path),
    )
    assert profile_dir == "Default"


def test_resolve_profile_raises_on_no_match(tmp_path):
    local_state = tmp_path / "Local State"
    local_state.write_text(json.dumps({
        "profile": {
            "info_cache": {
                "Default": {"name": "Brian", "user_name": "brian@x.com"},
            }
        }
    }))

    with pytest.raises(RuntimeError, match="No chrome profile found"):
        resolve_profile(
            email="unknown@nowhere.com",
            browser="chrome",
            user_data_dir=str(tmp_path),
        )


def test_resolve_profile_raises_when_no_data_dir(monkeypatch):
    """With no user_data_dir and no default found, should raise."""
    monkeypatch.setattr(
        "cookie_monster.browser_profiles.default_user_data_dir",
        lambda browser: None,
    )

    with pytest.raises(RuntimeError, match="Cannot auto-detect profile"):
        resolve_profile(email="test@example.com", browser="chrome")


# ── list_profiles ────────────────────────────────────────────────────────────


def test_list_profiles_sorts_by_directory(tmp_path):
    local_state = tmp_path / "Local State"
    local_state.write_text(json.dumps({
        "profile": {
            "info_cache": {
                "Profile 2": {"name": "Z", "user_name": "z@example.com"},
                "Default": {"name": "A", "user_name": "a@example.com"},
                "Profile 1": {"name": "M", "user_name": "m@example.com"},
            }
        }
    }))

    profiles = list_profiles(str(tmp_path))
    dirs = [p["profile_directory"] for p in profiles]
    assert dirs == ["Default", "Profile 1", "Profile 2"]
