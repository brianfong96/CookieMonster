import json

from cookie_monster import cli
from cookie_monster.models import CapturedRequest


class DummyResponse:
    def __init__(self):
        self.status_code = 200
        self.headers = {"Content-Type": "application/json"}
        self.text = "{\"ok\": true}"


def test_main_capture_command_prints_summary(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["cookie-monster", "capture", "--duration", "1"])
    monkeypatch.setattr(
        "cookie_monster.cli.capture_requests",
        lambda config: [
            CapturedRequest("1", "GET", "https://example.com", {"Cookie": "x=1"}),
            CapturedRequest("2", "GET", "https://example.com", {"Cookie": "x=2"}),
        ],
    )

    cli.main()
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["captured"] == 2


def test_main_capture_launches_chrome_with_profile(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        [
            "cookie-monster",
            "capture",
            "--duration",
            "1",
            "--launch-chrome",
            "--user-data-dir",
            "/tmp/chrome-root",
            "--profile-directory",
            "Default",
            "--open-url",
            "https://supabase.com/dashboard/project/abc",
        ],
    )
    called = {}

    class DummyProc:
        def terminate(self):
            called["terminated"] = True

    def fake_launch(**kwargs):
        called["launch"] = kwargs
        return DummyProc()

    monkeypatch.setattr("cookie_monster.cli.launch_browser", fake_launch)
    monkeypatch.setattr("cookie_monster.cli.wait_for_debug_endpoint", lambda host, port: None)
    monkeypatch.setattr(
        "cookie_monster.cli.capture_requests",
        lambda config: [CapturedRequest("1", "GET", "https://example.com", {"Cookie": "x=1"})],
    )

    cli.main()
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["captured"] == 1
    assert called["launch"]["browser"] == "chrome"
    assert called["launch"]["user_data_dir"] == "/tmp/chrome-root"
    assert called["launch"]["profile_directory"] == "Default"
    assert called.get("terminated") is True


def test_main_replay_command_prints_preview(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        [
            "cookie-monster",
            "replay",
            "--request-url",
            "https://example.com/api",
            "--capture-file",
            "captures.jsonl",
        ],
    )
    monkeypatch.setattr("cookie_monster.cli.replay_with_capture", lambda config: DummyResponse())

    cli.main()
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["status_code"] == 200
    assert "ok" in data["body_preview"]


def test_main_capture_edge_uses_browser_path(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        [
            "cookie-monster",
            "capture",
            "--duration",
            "1",
            "--launch-chrome",
            "--browser",
            "edge",
            "--browser-path",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ],
    )
    called = {}

    class DummyProc:
        def terminate(self):
            called["terminated"] = True

    def fake_launch(**kwargs):
        called["launch"] = kwargs
        return DummyProc()

    monkeypatch.setattr("cookie_monster.cli.launch_browser", fake_launch)
    monkeypatch.setattr("cookie_monster.cli.wait_for_debug_endpoint", lambda host, port: None)
    monkeypatch.setattr(
        "cookie_monster.cli.capture_requests",
        lambda config: [CapturedRequest("1", "GET", "https://example.com", {"Cookie": "x=1"})],
    )

    cli.main()
    _ = capsys.readouterr().out
    assert called["launch"]["browser"] == "edge"
    assert called["launch"]["browser_path"].endswith("Microsoft Edge")


def test_ui_command_starts_server_without_open(monkeypatch):
    monkeypatch.setattr("sys.argv", ["cookie-monster", "ui", "--no-open", "--host", "127.0.0.1", "--port", "9999"])
    called = {}
    monkeypatch.setattr("cookie_monster.cli.serve_api", lambda host, port: called.update({"host": host, "port": port}))
    monkeypatch.setattr("cookie_monster.cli.webbrowser.open", lambda *_: (_ for _ in ()).throw(AssertionError("should not open")))
    cli.main()
    assert called["host"] == "127.0.0.1"
    assert called["port"] == 9999
