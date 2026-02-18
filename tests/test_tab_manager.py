"""Tests for the tab_manager module and related CLI commands."""

import json

from cookie_monster import cli
from cookie_monster.tab_manager import TabManager, TabManagerConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeCDPClient:
    """Minimal CDP stub that records method calls."""

    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.connected = False
        self.commands: list[tuple[str, dict]] = []
        self._events: list[dict | None] = []

    def connect(self):
        self.connected = True

    def close(self):
        self.connected = False

    def send_command(self, method, params=None):
        self.commands.append((method, params or {}))
        if method == "Page.enable":
            return {}
        if method == "Page.navigate":
            return {"frameId": "F1"}
        if method == "Page.reload":
            return {}
        if method == "Target.createTarget":
            return {"targetId": "new-tab-1"}
        if method == "Target.closeTarget":
            return {"success": True}
        if method == "Target.getTargets":
            return {"targetInfos": []}
        return {}

    def enable_page_events(self):
        self.send_command("Page.enable", {})

    def reload(self, ignore_cache=False):
        self.send_command("Page.reload", {"ignoreCache": ignore_cache})
        return {}

    def navigate(self, url):
        self.send_command("Page.navigate", {"url": url})
        return {"frameId": "F1"}

    def wait_for_load(self, timeout_seconds=30.0):
        return True

    def create_target(self, url="about:blank"):
        result = self.send_command("Target.createTarget", {"url": url})
        return result.get("targetId", "")

    def close_target(self, target_id):
        result = self.send_command("Target.closeTarget", {"targetId": target_id})
        return result.get("success", False)

    def read_event(self, timeout_seconds=1.0):
        if self._events:
            return self._events.pop(0)
        return None


FAKE_TARGETS = [
    {"id": "AAA", "title": "GitHub", "url": "https://github.com/dashboard", "type": "page",
     "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/AAA"},
    {"id": "BBB", "title": "Google", "url": "https://www.google.com", "type": "page",
     "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/BBB"},
]


# ---------------------------------------------------------------------------
# TabManager unit tests
# ---------------------------------------------------------------------------

def test_list_tabs_returns_handles(monkeypatch):
    monkeypatch.setattr(
        "cookie_monster.tab_manager.list_page_targets",
        lambda host, port: FAKE_TARGETS,
    )
    mgr = TabManager(TabManagerConfig())
    tabs = mgr.list_tabs()
    assert len(tabs) == 2
    assert tabs[0].target_id == "AAA"
    assert tabs[1].url == "https://www.google.com"


def test_refresh_calls_reload(monkeypatch):
    monkeypatch.setattr(
        "cookie_monster.tab_manager.list_page_targets",
        lambda host, port: FAKE_TARGETS,
    )
    fake_client = FakeCDPClient("ws://fake")
    monkeypatch.setattr(
        "cookie_monster.tab_manager.CDPClient",
        lambda ws_url: fake_client,
    )
    mgr = TabManager(TabManagerConfig())
    loaded = mgr.refresh("AAA")
    assert loaded is True
    methods = [cmd[0] for cmd in fake_client.commands]
    assert "Page.enable" in methods
    assert "Page.reload" in methods
    mgr.close()


def test_navigate_calls_page_navigate(monkeypatch):
    monkeypatch.setattr(
        "cookie_monster.tab_manager.list_page_targets",
        lambda host, port: FAKE_TARGETS,
    )
    fake_client = FakeCDPClient("ws://fake")
    monkeypatch.setattr(
        "cookie_monster.tab_manager.CDPClient",
        lambda ws_url: fake_client,
    )
    mgr = TabManager(TabManagerConfig())
    loaded = mgr.navigate("AAA", "https://example.com")
    assert loaded is True
    nav_cmds = [cmd for cmd in fake_client.commands if cmd[0] == "Page.navigate"]
    assert len(nav_cmds) == 1
    assert nav_cmds[0][1]["url"] == "https://example.com"
    mgr.close()


def test_open_tab_creates_target(monkeypatch):
    monkeypatch.setattr(
        "cookie_monster.tab_manager.list_page_targets",
        lambda host, port: FAKE_TARGETS,
    )
    fake_client = FakeCDPClient("ws://fake")
    monkeypatch.setattr(
        "cookie_monster.tab_manager.CDPClient",
        lambda ws_url: fake_client,
    )
    mgr = TabManager(TabManagerConfig())
    handle = mgr.open_tab("https://test.com")
    assert handle.target_id == "new-tab-1"
    assert handle.url == "https://test.com"
    mgr.close()


def test_close_tab_drops_client(monkeypatch):
    monkeypatch.setattr(
        "cookie_monster.tab_manager.list_page_targets",
        lambda host, port: FAKE_TARGETS,
    )
    fake_client = FakeCDPClient("ws://fake")
    monkeypatch.setattr(
        "cookie_monster.tab_manager.CDPClient",
        lambda ws_url: fake_client,
    )
    mgr = TabManager(TabManagerConfig())
    success = mgr.close_tab("BBB")
    assert success is True
    mgr.close()


def test_context_manager_disconnects(monkeypatch):
    monkeypatch.setattr(
        "cookie_monster.tab_manager.list_page_targets",
        lambda host, port: FAKE_TARGETS,
    )
    fake_client = FakeCDPClient("ws://fake")
    monkeypatch.setattr(
        "cookie_monster.tab_manager.CDPClient",
        lambda ws_url: fake_client,
    )
    with TabManager(TabManagerConfig()) as mgr:
        mgr.refresh("AAA")
    assert fake_client.connected is False


def test_refresh_with_ignore_cache(monkeypatch):
    monkeypatch.setattr(
        "cookie_monster.tab_manager.list_page_targets",
        lambda host, port: FAKE_TARGETS,
    )
    fake_client = FakeCDPClient("ws://fake")
    monkeypatch.setattr(
        "cookie_monster.tab_manager.CDPClient",
        lambda ws_url: fake_client,
    )
    mgr = TabManager(TabManagerConfig(ignore_cache=True))
    mgr.refresh("AAA")
    reload_cmds = [cmd for cmd in fake_client.commands if cmd[0] == "Page.reload"]
    assert len(reload_cmds) == 1
    assert reload_cmds[0][1]["ignoreCache"] is True
    mgr.close()


# ---------------------------------------------------------------------------
# CLI command tests
# ---------------------------------------------------------------------------

def test_refresh_tab_cli_command(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        ["cookie-monster", "refresh-tab", "--target-hint", "github"],
    )

    fake_client = FakeCDPClient("ws://fake")
    monkeypatch.setattr(
        "cookie_monster.tab_manager.list_page_targets",
        lambda host, port: FAKE_TARGETS,
    )
    monkeypatch.setattr(
        "cookie_monster.tab_manager.CDPClient",
        lambda ws_url: fake_client,
    )

    cli.main()
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["refreshed"] is True
    assert data["target_id"] == "AAA"


def test_navigate_tab_cli_command(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        ["cookie-monster", "navigate-tab", "https://example.com", "--target-hint", "google"],
    )

    fake_client = FakeCDPClient("ws://fake")
    monkeypatch.setattr(
        "cookie_monster.tab_manager.list_page_targets",
        lambda host, port: FAKE_TARGETS,
    )
    monkeypatch.setattr(
        "cookie_monster.tab_manager.CDPClient",
        lambda ws_url: fake_client,
    )

    cli.main()
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["url"] == "https://example.com"
    assert data["target_id"] == "BBB"


def test_open_tab_cli_command(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        ["cookie-monster", "open-tab", "--url", "https://new-page.test"],
    )

    fake_client = FakeCDPClient("ws://fake")
    monkeypatch.setattr(
        "cookie_monster.tab_manager.list_page_targets",
        lambda host, port: FAKE_TARGETS,
    )
    monkeypatch.setattr(
        "cookie_monster.tab_manager.CDPClient",
        lambda ws_url: fake_client,
    )

    cli.main()
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["target_id"] == "new-tab-1"
    assert data["url"] == "https://new-page.test"


def test_close_tab_cli_command(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        ["cookie-monster", "close-tab", "--target-id", "BBB"],
    )

    fake_client = FakeCDPClient("ws://fake")
    monkeypatch.setattr(
        "cookie_monster.tab_manager.list_page_targets",
        lambda host, port: FAKE_TARGETS,
    )
    monkeypatch.setattr(
        "cookie_monster.tab_manager.CDPClient",
        lambda ws_url: fake_client,
    )

    cli.main()
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["closed"] is True
    assert data["target_id"] == "BBB"
