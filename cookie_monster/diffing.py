from __future__ import annotations

from dataclasses import dataclass

from .models import CapturedRequest
from .storage import load_captures


@dataclass
class CaptureDiff:
    headers_added: list[str]
    headers_removed: list[str]
    method_changed: bool


def _signature(capture: CapturedRequest) -> tuple[set[str], str]:
    return ({k.lower() for k in capture.headers.keys()}, capture.method.upper())


def compare_capture_files(path_a: str, path_b: str, encryption_key_a: str | None = None, encryption_key_b: str | None = None) -> CaptureDiff:
    caps_a = load_captures(path_a, encryption_key=encryption_key_a)
    caps_b = load_captures(path_b, encryption_key=encryption_key_b)
    if not caps_a or not caps_b:
        raise RuntimeError("Both capture files must contain at least one record")

    headers_a, method_a = _signature(caps_a[-1])
    headers_b, method_b = _signature(caps_b[-1])

    return CaptureDiff(
        headers_added=sorted(headers_b - headers_a),
        headers_removed=sorted(headers_a - headers_b),
        method_changed=method_a != method_b,
    )
