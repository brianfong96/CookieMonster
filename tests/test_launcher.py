from cookie_monster import chrome_launcher


class DummyProc:
    pass


def test_launch_chrome_includes_profile_directory(monkeypatch):
    captured = {}

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return DummyProc()

    # Force non-Windows path so we exercise the simple list-of-args branch.
    monkeypatch.setattr("cookie_monster.chrome_launcher.platform.system", lambda: "Darwin")
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


def test_launch_browser_windows_handles_spaces(monkeypatch):
    """On Windows, paths with spaces should be converted to 8.3 short form."""
    captured = {}

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return DummyProc()

    monkeypatch.setattr("cookie_monster.chrome_launcher.platform.system", lambda: "Windows")
    monkeypatch.setattr("cookie_monster.chrome_launcher.subprocess.Popen", fake_popen)

    # Mock GetShortPathNameW to return a predictable short path.
    def fake_short_path(path, buf, size):
        if " " in path:
            short = path.replace("User Data", "USERDA~1")
            # Write into pre-existing buffer (buf is already allocated)
            for i, ch in enumerate(short):
                buf[i] = ch
            buf[len(short)] = "\0"
            return len(short)
        return 0

    monkeypatch.setattr("cookie_monster.chrome_launcher.ctypes.windll.kernel32.GetShortPathNameW", fake_short_path)

    proc = chrome_launcher.launch_browser(
        browser="chrome",
        browser_path="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        host="127.0.0.1",
        port=9222,
        user_data_dir="C:\\Users\\test\\AppData\\Local\\Google\\Chrome\\User Data",
        profile_directory="Default",
        open_url="https://example.com",
        headless=False,
    )

    assert isinstance(proc, DummyProc)
    args = captured["args"]

    # The user-data-dir should have the short path (no spaces).
    udd_arg = [a for a in args if a.startswith("--user-data-dir=")][0]
    assert "USERDA~1" in udd_arg
    assert "User Data" not in udd_arg

    # --enable-logging should be automatically added on Windows.
    assert "--enable-logging" in args

    # CREATE_NEW_CONSOLE should be in Popen kwargs.
    import subprocess
    assert captured["kwargs"].get("creationflags") == subprocess.CREATE_NEW_CONSOLE


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


# ── browser_is_reachable ─────────────────────────────────────────────────────


def test_browser_is_reachable_true(monkeypatch):
    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(
        "cookie_monster.chrome_launcher.urllib.request.urlopen",
        lambda url, timeout=1: FakeResp(),
    )
    assert chrome_launcher.browser_is_reachable("127.0.0.1", 9222) is True


def test_browser_is_reachable_false(monkeypatch):
    monkeypatch.setattr(
        "cookie_monster.chrome_launcher.urllib.request.urlopen",
        lambda url, timeout=1: (_ for _ in ()).throw(ConnectionError("nope")),
    )
    assert chrome_launcher.browser_is_reachable("127.0.0.1", 9222) is False


# ── is_browser_process_running ───────────────────────────────────────────────


def test_is_browser_process_running_windows(monkeypatch):
    monkeypatch.setattr("cookie_monster.chrome_launcher.platform.system", lambda: "Windows")

    class FakeResult:
        stdout = "chrome.exe   1234 Console  0  12,345 K"

    monkeypatch.setattr(
        "cookie_monster.chrome_launcher.subprocess.run",
        lambda *a, **kw: FakeResult(),
    )
    assert chrome_launcher.is_browser_process_running("chrome") is True


def test_is_browser_process_running_not_found(monkeypatch):
    monkeypatch.setattr("cookie_monster.chrome_launcher.platform.system", lambda: "Windows")

    class FakeResult:
        stdout = "INFO: No tasks are running which match the specified criteria."

    monkeypatch.setattr(
        "cookie_monster.chrome_launcher.subprocess.run",
        lambda *a, **kw: FakeResult(),
    )
    assert chrome_launcher.is_browser_process_running("chrome") is False
