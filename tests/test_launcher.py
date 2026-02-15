from cookie_monster import chrome_launcher


class DummyProc:
    pass


def test_launch_chrome_includes_profile_directory(monkeypatch):
    captured = {}

    def fake_popen(args):
        captured["args"] = args
        return DummyProc()

    monkeypatch.setattr("cookie_monster.chrome_launcher.subprocess.Popen", fake_popen)

    proc = chrome_launcher.launch_chrome(
        chrome_path="/path/chrome",
        host="127.0.0.1",
        port=9222,
        user_data_dir="/tmp/profile-root",
        profile_directory="Profile 1",
        open_url="https://example.com",
        headless=True,
    )

    assert isinstance(proc, DummyProc)
    args = captured["args"]
    assert "--profile-directory=Profile 1" in args
    assert "--remote-allow-origins=*" in args
    assert "--headless=new" in args
    assert "--new-window" in args


def test_wait_for_debug_endpoint_retries(monkeypatch):
    state = {"count": 0}

    class DummyResp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_open(url, timeout=1):
        state["count"] += 1
        if state["count"] < 3:
            raise ConnectionError("not ready")
        return DummyResp()

    monkeypatch.setattr("cookie_monster.chrome_launcher.urllib.request.urlopen", fake_open)
    monkeypatch.setattr("cookie_monster.chrome_launcher.time.sleep", lambda *_: None)

    chrome_launcher.wait_for_debug_endpoint("127.0.0.1", 9222, timeout_seconds=2)
    assert state["count"] == 3


def test_detect_edge_path_on_macos(monkeypatch):
    monkeypatch.setattr("cookie_monster.chrome_launcher.platform.system", lambda: "Darwin")
    monkeypatch.setattr(
        "cookie_monster.chrome_launcher.os.path.exists",
        lambda p: p == "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    )
    path = chrome_launcher.detect_browser_path("edge")
    assert path == "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
