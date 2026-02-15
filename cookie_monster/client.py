from __future__ import annotations

import asyncio
from dataclasses import asdict

from .browser_profiles import list_profiles
from .capture import capture_requests
from .chrome_discovery import list_page_targets
from .config import CaptureConfig, ReplayConfig
from .doctor import run_doctor
from .exceptions import CaptureError, ReplayError, ReplayPolicyError
from .hooks import CookieMonsterHooks
from .policy import ReplayPolicy
from .recipes import Recipe, list_recipes, load_recipe, save_recipe
from .replay import replay_with_capture
from .results import CaptureResult, ReplayResult, SessionHealthResult
from .session_health import analyze_session_health


class CookieMonsterClient:
    """Stable library API for programmatic access to CookieMonster."""

    def __init__(self, hooks: CookieMonsterHooks | None = None, policy: ReplayPolicy | None = None) -> None:
        self.hooks = hooks
        self.policy = policy or ReplayPolicy()

    def capture(self, config: CaptureConfig) -> CaptureResult:
        try:
            if self.hooks:
                self.hooks.on_capture_start()
            captures = capture_requests(config)
            if self.hooks:
                for item in captures:
                    self.hooks.on_capture_item(item)
                self.hooks.on_capture_end(len(captures))
            return CaptureResult(captures=captures, output_file=config.output_file)
        except Exception as exc:  # noqa: BLE001
            raise CaptureError(str(exc)) from exc

    def replay(self, config: ReplayConfig) -> ReplayResult:
        try:
            self.policy.validate(config.request_url)
        except Exception as exc:  # noqa: BLE001
            raise ReplayPolicyError(str(exc)) from exc

        try:
            if self.hooks:
                self.hooks.on_replay_attempt(1, max(1, config.retry_attempts))
            response = replay_with_capture(config)
            if self.hooks:
                self.hooks.on_replay_end(response.status_code)
            return ReplayResult(
                status_code=response.status_code,
                content_type=response.headers.get("Content-Type", ""),
                body_preview=response.text[:400],
                request_url=config.request_url,
            )
        except Exception as exc:  # noqa: BLE001
            raise ReplayError(str(exc)) from exc

    async def capture_async(self, config: CaptureConfig) -> CaptureResult:
        return await asyncio.to_thread(self.capture, config)

    async def replay_async(self, config: ReplayConfig) -> ReplayResult:
        return await asyncio.to_thread(self.replay, config)

    def targets(self, host: str = "127.0.0.1", port: int = 9222) -> list[dict]:
        return list_page_targets(host, port)

    def profiles(self, user_data_dir: str) -> list[dict]:
        return list_profiles(user_data_dir)

    def doctor(self, browser: str, host: str = "127.0.0.1", port: int = 9222, user_data_dir: str | None = None) -> dict:
        return run_doctor(browser, host, port, user_data_dir)

    def session_health(self, capture_file: str, encryption_key: str | None = None) -> SessionHealthResult:
        from .storage import load_captures

        captures = load_captures(capture_file, encryption_key=encryption_key)
        return analyze_session_health(captures)

    def save_recipe(self, recipe: Recipe, base_dir: str | None = None) -> str:
        return str(save_recipe(recipe, base_dir=base_dir))

    def load_recipe(self, name: str, base_dir: str | None = None) -> Recipe:
        return load_recipe(name, base_dir=base_dir)

    def list_recipes(self, base_dir: str | None = None) -> list[str]:
        return list_recipes(base_dir=base_dir)

    def recipe_to_dict(self, recipe: Recipe) -> dict:
        return {
            "name": recipe.name,
            "capture": asdict(recipe.capture),
            "replay": asdict(recipe.replay),
        }
