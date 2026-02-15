import pytest

from cookie_monster.chrome_discovery import get_websocket_debug_url, list_targets


def test_list_targets_retries_then_succeeds(monkeypatch):
    attempts = {"count": 0}

    def fake_read_json(url):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise ConnectionError("not ready")
        return [{"type": "page", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/1"}]

    monkeypatch.setattr("cookie_monster.chrome_discovery._read_json", fake_read_json)
    targets = list_targets("127.0.0.1", 9222, retries=4, retry_delay_seconds=0)

    assert len(targets) == 1
    assert attempts["count"] == 3


def test_get_websocket_debug_url_with_hint(monkeypatch):
    monkeypatch.setattr(
        "cookie_monster.chrome_discovery.list_targets",
        lambda host, port, retries=1, retry_delay_seconds=0.5: [
            {
                "id": "a",
                "type": "page",
                "title": "Home",
                "url": "https://example.com",
                "webSocketDebuggerUrl": "ws://one",
            },
            {
                "id": "b",
                "type": "page",
                "title": "GitHub",
                "url": "https://github.com",
                "webSocketDebuggerUrl": "ws://two",
            },
        ],
    )

    ws = get_websocket_debug_url("127.0.0.1", 9222, hint="github")
    assert ws == "ws://two"


def test_get_websocket_debug_url_raises_if_no_pages(monkeypatch):
    monkeypatch.setattr(
        "cookie_monster.chrome_discovery.list_targets",
        lambda host, port, retries=1, retry_delay_seconds=0.5: [],
    )
    with pytest.raises(RuntimeError):
        get_websocket_debug_url("127.0.0.1", 9222)
