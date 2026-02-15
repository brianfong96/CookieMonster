from __future__ import annotations

import json
from pathlib import Path

from .crypto import decrypt_text, encrypt_text
from .models import CapturedRequest


def append_captures(path: str, captures: list[CapturedRequest], encryption_key: str | None = None) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as f:
        for capture in captures:
            line = json.dumps(capture.to_dict(), ensure_ascii=True)
            if encryption_key:
                line = encrypt_text(line, encryption_key)
            f.write(line + "\n")


def load_captures(path: str, encryption_key: str | None = None) -> list[CapturedRequest]:
    capture_file = Path(path)
    if not capture_file.exists():
        raise FileNotFoundError(f"Capture file not found: {path}")

    captures: list[CapturedRequest] = []
    with capture_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("ENC:"):
                if not encryption_key:
                    raise RuntimeError(
                        "Capture file is encrypted. Provide key via --encryption-key or --encryption-key-env."
                    )
                line = decrypt_text(line, encryption_key)
            captures.append(CapturedRequest.from_dict(json.loads(line)))
    return captures
