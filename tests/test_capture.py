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
                        "postData": '{"x":1}',
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

    def fake_append(path, captures, encryption_key=None):
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
    monkeypatch.setattr("cookie_monster.capture.append_captures", lambda path, captures, encryption_key=None: None)

    cfg = CaptureConfig(
        duration_seconds=1,
        max_records=10,
        target_hint="github.com",
        include_all_headers=True,
    )

    captures = capture_requests(cfg)
    assert captures
    assert "Accept" in captures[0].headers


def test_capture_post_data_when_enabled(monkeypatch):
    monkeypatch.setattr("cookie_monster.capture.get_websocket_debug_url", lambda *args, **kwargs: "ws://fake")
    monkeypatch.setattr("cookie_monster.capture.CDPClient", FakeCDPClient)
    monkeypatch.setattr("cookie_monster.capture.append_captures", lambda path, captures, encryption_key=None: None)

    cfg = CaptureConfig(
        duration_seconds=1,
        max_records=10,
        target_hint="github.com",
        capture_post_data=True,
    )
    captures = capture_requests(cfg)
    assert captures
    assert captures[0].post_data == '{"x":1}'


class FakeCDPNoInlinePostData(FakeCDPClient):
    def __init__(self, ws_url):
        super().__init__(ws_url)
        self.events[0]["params"]["request"].pop("postData", None)

    def send_command(self, method, params):
        if method == "Network.enable":
            return {}
        if method == "Network.getRequestPostData":
            return {"postData": "fallback-body"}
        raise AssertionError(f"unexpected method {method}")


def test_capture_post_data_falls_back_to_cdp_query(monkeypatch):
    monkeypatch.setattr("cookie_monster.capture.get_websocket_debug_url", lambda *args, **kwargs: "ws://fake")
    monkeypatch.setattr("cookie_monster.capture.CDPClient", FakeCDPNoInlinePostData)
    monkeypatch.setattr("cookie_monster.capture.append_captures", lambda path, captures, encryption_key=None: None)

    cfg = CaptureConfig(
        duration_seconds=1,
        max_records=10,
        target_hint="github.com",
        capture_post_data=True,
    )
    captures = capture_requests(cfg)
    assert captures
    assert captures[0].post_data == "fallback-body"
