import json
import pytest

from cookie_monster.config import ReplayConfig
from cookie_monster.models import CapturedRequest
from cookie_monster.replay import _pick_capture, _sanitize_headers, replay_with_capture


class DummyResponse:
    def __init__(self, status_code=200, headers=None, text="ok"):
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "application/json"}
        self.text = text


def test_pick_capture_uses_latest_matching_url_and_method():
    captures = [
        CapturedRequest("1", "GET", "https://x.io/a", {"Cookie": "a"}),
        CapturedRequest("2", "POST", "https://x.io/a", {"Cookie": "b"}),
        CapturedRequest("3", "GET", "https://x.io/a?x=1", {"Cookie": "c"}),
    ]
    cfg = ReplayConfig(
        capture_file="unused",
        request_url="https://target",
        method="GET",
        url_contains="/a",
    )

    chosen = _pick_capture(captures, cfg)
    assert chosen.request_id == "3"


def test_sanitize_headers_drops_transport_specific_headers():
    headers = {
        "Host": "x.io",
        "content-length": "9",
        "Connection": "keep-alive",
        "Cookie": "session=1",
    }
    cleaned = _sanitize_headers(headers)
    assert "Host" not in cleaned
    assert "content-length" not in cleaned
    assert "Connection" not in cleaned
    assert cleaned["Cookie"] == "session=1"


def test_replay_uses_loaded_capture_and_writes_output(tmp_path, monkeypatch):
    capture_file = tmp_path / "caps.jsonl"
    capture_file.write_text(
        json.dumps(
            {
                "request_id": "10",
                "method": "GET",
                "url": "https://github.com/api",
                "headers": {"Cookie": "x=1", "Host": "github.com"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    called = {}

    def fake_request(method, url, headers, timeout, data=None, json=None):
        called["method"] = method
        called["url"] = url
        called["headers"] = headers
        called["timeout"] = timeout
        called["data"] = data
        called["json"] = json
        return DummyResponse(status_code=200, text='{"ok":true}')

    monkeypatch.setattr("cookie_monster.replay.requests.request", fake_request)

    output_file = tmp_path / "response.json"
    cfg = ReplayConfig(
        capture_file=str(capture_file),
        request_url="https://github.com/settings/profile",
        method="GET",
        url_contains="github.com",
        output_file=str(output_file),
    )

    response = replay_with_capture(cfg)

    assert response.status_code == 200
    assert called["method"] == "GET"
    assert called["url"] == "https://github.com/settings/profile"
    assert "Host" not in called["headers"]
    assert called["headers"]["Cookie"] == "x=1"
    assert output_file.exists()


def test_replay_enforces_allowed_domain(tmp_path):
    capture_file = tmp_path / "caps.jsonl"
    capture_file.write_text(
        json.dumps(
            {
                "request_id": "10",
                "method": "GET",
                "url": "https://github.com/api",
                "headers": {"Cookie": "x=1"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    cfg = ReplayConfig(
        capture_file=str(capture_file),
        request_url="https://example.com/api",
        method="GET",
        url_contains="github.com",
        allowed_domains=["github.com"],
        enforce_capture_host=False,
    )
    with pytest.raises(RuntimeError):
        replay_with_capture(cfg)
