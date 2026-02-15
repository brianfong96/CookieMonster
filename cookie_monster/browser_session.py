from __future__ import annotations

from dataclasses import dataclass
from subprocess import Popen

from .chrome_launcher import launch_browser, wait_for_debug_endpoint


@dataclass
class BrowserLaunchConfig:
    browser: str = "chrome"
    browser_path: str | None = None
    host: str = "127.0.0.1"
    port: int = 9222
    user_data_dir: str | None = None
    profile_directory: str | None = None
    open_url: str | None = None
    headless: bool = False


class BrowserSession:
    def __init__(self, config: BrowserLaunchConfig) -> None:
        self.config = config
        self._proc: Popen[bytes] | None = None

    def __enter__(self) -> "BrowserSession":
        self._proc = launch_browser(
            browser=self.config.browser,
            browser_path=self.config.browser_path,
            host=self.config.host,
            port=self.config.port,
            user_data_dir=self.config.user_data_dir,
            profile_directory=self.config.profile_directory,
            open_url=self.config.open_url,
            headless=self.config.headless,
        )
        wait_for_debug_endpoint(self.config.host, self.config.port)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False

    def close(self) -> None:
        if self._proc is not None:
            self._proc.terminate()
            self._proc = None
