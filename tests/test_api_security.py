from __future__ import annotations

from io import BytesIO

import pytest

from cookie_monster import api_server
from cookie_monster.config import ReplayConfig
from cookie_monster.models import CapturedRequest


class _FakeHandler:
    def __init__(self, body: bytes, content_length: int) -> None:
        self.headers = {"Content-Length": str(content_length)}
        self.rfile = BytesIO(body)


def test_validate_http_url_accepts_https():
    assert api_server._validate_http_url("https://example.com/path") == "https://example.com/path"


def test_validate_http_url_rejects_non_http_scheme():
    with pytest.raises(ValueError):
        api_server._validate_http_url("file:///etc/passwd")


def test_read_json_body_rejects_large_payload():
    handler = _FakeHandler(body=b"{}", content_length=api_server.MAX_JSON_BODY_BYTES + 1)
    with pytest.raises(ValueError):
        api_server._read_json_body(handler)  # noqa: SLF001


def test_enforce_local_bind_rejects_non_loopback_without_override(monkeypatch):
    monkeypatch.delenv("COOKIE_MONSTER_ALLOW_REMOTE", raising=False)
    with pytest.raises(RuntimeError):
        api_server._enforce_local_bind("0.0.0.0")


def test_enforce_local_bind_allows_non_loopback_with_override(monkeypatch):
    monkeypatch.setenv("COOKIE_MONSTER_ALLOW_REMOTE", "1")
    api_server._enforce_local_bind("0.0.0.0")


def test_safe_replay_config_redacts_encryption_key():
    config = ReplayConfig(capture_file="captures.jsonl", request_url="https://example.com", encryption_key="secret")
    payload = api_server._safe_replay_config(config)
    assert payload["encryption_key"] == "***REDACTED***"


def test_is_authorized_with_matching_token():
    handler = _FakeHandler(body=b"{}", content_length=2)
    handler.headers["X-CM-Token"] = "abc123"
    assert api_server._is_authorized(handler, "abc123") is True


def test_is_authorized_rejects_invalid_token():
    handler = _FakeHandler(body=b"{}", content_length=2)
    handler.headers["X-CM-Token"] = "wrong"
    assert api_server._is_authorized(handler, "abc123") is False


def test_capture_sample_redacts_headers_by_default():
    captures = [CapturedRequest("1", "GET", "https://example.com", {"Authorization": "Bearer token"})]
    sample = api_server._capture_sample(captures, redact_output=True)
    assert sample[0]["headers"]["Authorization"] == "***REDACTED***"
