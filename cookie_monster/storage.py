from __future__ import annotations

import json
from pathlib import Path

from .models import CapturedRequest


def append_captures(path: str, captures: list[CapturedRequest]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as f:
        for capture in captures:
            f.write(json.dumps(capture.to_dict(), ensure_ascii=True) + "\n")


def load_captures(path: str) -> list[CapturedRequest]:
    capture_file = Path(path)
    if not capture_file.exists():
        raise FileNotFoundError(f"Capture file not found: {path}")

    captures: list[CapturedRequest] = []
    with capture_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            captures.append(CapturedRequest.from_dict(json.loads(line)))
    return captures
