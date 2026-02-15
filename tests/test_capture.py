from cookie_monster.capture import capture_requests
from cookie_monster.config import CaptureConfig


class FakeCDPClient:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.events = [
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": "1",
                    "type": "XHR",
                    "request": {
                        "method": "GET",
                        "url": "https://github.com/settings/profile",
                        "headers": {"Accept": "application/json"},
                    },
                },
            },
            {
                "method": "Network.requestWillBeSentExtraInfo",
                "params": {
                    "requestId": "1",
                    "headers": {
                        "Cookie": "user_session=abc",
                        "Authorization": "Bearer secret",
                    },
                },
            },
            None,
        ]

    def connect(self):
        return None

    def close(self):
        return None

    def send_command(self, method, params):
        assert method == "Network.enable"
        return {}

    def read_event(self, timeout_seconds=1.0):
        if not self.events:
            return None
        return self.events.pop(0)


def test_capture_filters_to_auth_headers_and_persists(monkeypatch):
    saved = {}

    def fake_append(path, captures):
        saved["path"] = path
        saved["captures"] = captures

    monkeypatch.setattr("cookie_monster.capture.get_websocket_debug_url", lambda *args, **kwargs: "ws://fake")
    monkeypatch.setattr("cookie_monster.capture.CDPClient", FakeCDPClient)
    monkeypatch.setattr("cookie_monster.capture.append_captures", fake_append)

    cfg = CaptureConfig(
        duration_seconds=1,
        max_records=10,
        output_file="out.jsonl",
        target_hint="github.com",
    )

    captures = capture_requests(cfg)

    assert len(captures) == 1
    assert captures[0].url == "https://github.com/settings/profile"
    assert "Cookie" in captures[0].headers
    assert "Authorization" in captures[0].headers
    assert "Accept" not in captures[0].headers
    assert saved["path"] == "out.jsonl"


def test_capture_all_headers_mode_keeps_non_auth_headers(monkeypatch):
    monkeypatch.setattr("cookie_monster.capture.get_websocket_debug_url", lambda *args, **kwargs: "ws://fake")
    monkeypatch.setattr("cookie_monster.capture.CDPClient", FakeCDPClient)
    monkeypatch.setattr("cookie_monster.capture.append_captures", lambda path, captures: None)

    cfg = CaptureConfig(
        duration_seconds=1,
        max_records=10,
        target_hint="github.com",
        include_all_headers=True,
    )

    captures = capture_requests(cfg)
    assert captures
    assert "Accept" in captures[0].headers
