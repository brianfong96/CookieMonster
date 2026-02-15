import asyncio

from cookie_monster.client import CookieMonsterClient
from cookie_monster.config import CaptureConfig, ReplayConfig
from cookie_monster.models import CapturedRequest
from cookie_monster.policy import ReplayPolicy
from cookie_monster.recipes import Recipe


class HookRecorder:
    def __init__(self):
        self.calls = []

    def on_capture_start(self):
        self.calls.append("capture_start")

    def on_capture_item(self, capture):
        self.calls.append(f"capture_item:{capture.request_id}")

    def on_capture_end(self, total):
        self.calls.append(f"capture_end:{total}")

    def on_replay_attempt(self, attempt, max_attempts):
        self.calls.append(f"replay_attempt:{attempt}/{max_attempts}")

    def on_replay_end(self, status_code):
        self.calls.append(f"replay_end:{status_code}")


def test_client_capture_and_replay(monkeypatch):
    hooks = HookRecorder()
    client = CookieMonsterClient(hooks=hooks, policy=ReplayPolicy(allowed_domains=["example.com"]))

    monkeypatch.setattr(
        "cookie_monster.client.capture_requests",
        lambda cfg: [CapturedRequest("1", "GET", "https://example.com", {"Cookie": "x"})],
    )

    class R:
        status_code = 200
        headers = {"Content-Type": "application/json"}
        text = '{"ok":true}'

    monkeypatch.setattr("cookie_monster.client.replay_with_capture", lambda cfg: R())

    cap = client.capture(CaptureConfig(output_file="x.jsonl"))
    rep = client.replay(ReplayConfig(capture_file="x.jsonl", request_url="https://example.com", enforce_capture_host=False))

    assert cap.count == 1
    assert rep.status_code == 200
    assert "capture_start" in hooks.calls
    assert any(c.startswith("replay_end") for c in hooks.calls)


def test_client_replay_policy_block():
    client = CookieMonsterClient(policy=ReplayPolicy(allowed_domains=["example.com"]))
    try:
        client.replay(ReplayConfig(capture_file="x", request_url="https://blocked.com", enforce_capture_host=False))
    except Exception as exc:  # noqa: BLE001
        assert "policy" in exc.__class__.__name__.lower()


def test_client_async_methods(monkeypatch):
    client = CookieMonsterClient()
    monkeypatch.setattr(
        "cookie_monster.client.capture_requests",
        lambda cfg: [CapturedRequest("1", "GET", "https://example.com", {"Cookie": "x"})],
    )

    class R:
        status_code = 200
        headers = {"Content-Type": "application/json"}
        text = '{"ok":true}'

    monkeypatch.setattr("cookie_monster.client.replay_with_capture", lambda cfg: R())

    cap = asyncio.run(client.capture_async(CaptureConfig(output_file="x.jsonl")))
    rep = asyncio.run(client.replay_async(ReplayConfig(capture_file="x.jsonl", request_url="https://example.com", enforce_capture_host=False)))
    assert cap.count == 1
    assert rep.status_code == 200


def test_recipe_roundtrip(tmp_path):
    client = CookieMonsterClient()
    recipe = Recipe(
        name="demo",
        capture=CaptureConfig(output_file="caps.jsonl", target_hint="example.com"),
        replay=ReplayConfig(capture_file="caps.jsonl", request_url="https://example.com", enforce_capture_host=False),
    )
    saved = client.save_recipe(recipe, base_dir=str(tmp_path))
    assert saved.endswith("demo.json")
    loaded = client.load_recipe("demo", base_dir=str(tmp_path))
    assert loaded.name == "demo"
    assert "demo" in client.list_recipes(base_dir=str(tmp_path))
