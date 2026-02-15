import json
from datetime import UTC, datetime, timedelta

from cookie_monster.diffing import compare_capture_files
from cookie_monster.models import CapturedRequest
from cookie_monster.session_health import analyze_session_health
from cookie_monster.storage import append_captures


def _jwt_with_exp(exp: int) -> str:
    import base64

    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    return f"{header}.{payload}.sig"


def test_session_health_detects_bearer_and_cookie():
    exp = int((datetime.now(UTC) + timedelta(minutes=10)).timestamp())
    token = _jwt_with_exp(exp)
    captures = [
        CapturedRequest("1", "GET", "https://x", {"Cookie": "a=b", "Authorization": f"Bearer {token}"})
    ]
    health = analyze_session_health(captures)
    assert health.has_cookie is True
    assert health.bearer_token_count == 1
    assert health.jwt_expired is False


def test_compare_capture_files(tmp_path):
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    append_captures(str(a), [CapturedRequest("1", "GET", "https://x", {"Cookie": "x"})])
    append_captures(str(b), [CapturedRequest("2", "POST", "https://x", {"Cookie": "x", "Authorization": "b"})])

    diff = compare_capture_files(str(a), str(b))
    assert "authorization" in diff.headers_added
    assert diff.method_changed is True
