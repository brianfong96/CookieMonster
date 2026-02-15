import json

from cookie_monster import cli


class DummyResponse:
    def __init__(self):
        self.status_code = 200
        self.headers = {"Content-Type": "application/json"}
        self.text = "{\"ok\": true}"


def test_main_capture_command_prints_summary(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["cookie-monster", "capture", "--duration", "1"])
    monkeypatch.setattr("cookie_monster.cli.capture_requests", lambda config: [object(), object()])

    cli.main()
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["captured"] == 2


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
