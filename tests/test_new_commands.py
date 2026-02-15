import json

from cookie_monster import cli


def test_profile_list_command(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        ["cookie-monster", "profile-list", "--browser", "chrome", "--user-data-dir", "/tmp/chrome"],
    )
    monkeypatch.setattr(
        "cookie_monster.cli.list_profiles",
        lambda user_data_dir: [{"profile_directory": "Default", "name": "Brian", "email": "x@y.com"}],
    )
    cli.main()
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["profiles"][0]["profile_directory"] == "Default"


def test_list_targets_command(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["cookie-monster", "list-targets"])
    monkeypatch.setattr(
        "cookie_monster.cli.list_page_targets",
        lambda host, port: [{"id": "1", "title": "Tab", "url": "https://a", "type": "page"}],
    )
    cli.main()
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["count"] == 1


def test_doctor_command(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["cookie-monster", "doctor", "--browser", "chrome"])
    monkeypatch.setattr(
        "cookie_monster.cli.run_doctor",
        lambda browser, host, port, user_data_dir: {"browser": browser, "ok": True},
    )
    cli.main()
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["ok"] is True


def test_adapter_list_command(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["cookie-monster", "adapter-list"])
    cli.main()
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "supabase" in data["adapters"]
