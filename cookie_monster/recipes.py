from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import CaptureConfig, ReplayConfig


@dataclass
class Recipe:
    name: str
    capture: CaptureConfig
    replay: ReplayConfig


def _recipes_dir(base_dir: str | None = None) -> Path:
    root = Path(base_dir) if base_dir else Path.home() / ".cookie_monster" / "recipes"
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_recipe(recipe: Recipe, base_dir: str | None = None) -> Path:
    path = _recipes_dir(base_dir) / f"{recipe.name}.json"
    payload = {
        "name": recipe.name,
        "capture": asdict(recipe.capture),
        "replay": asdict(recipe.replay),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_recipe(name: str, base_dir: str | None = None) -> Recipe:
    path = _recipes_dir(base_dir) / f"{name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return Recipe(
        name=str(data["name"]),
        capture=CaptureConfig(**data["capture"]),
        replay=ReplayConfig(**data["replay"]),
    )


def list_recipes(base_dir: str | None = None) -> list[str]:
    return sorted(p.stem for p in _recipes_dir(base_dir).glob("*.json"))
