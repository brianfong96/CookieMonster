from cookie_monster.models import CapturedRequest
from cookie_monster.storage import append_captures, load_captures


def test_storage_roundtrip(tmp_path):
    out = tmp_path / "captures.jsonl"
    records = [
        CapturedRequest(
            request_id="1",
            method="GET",
            url="https://example.com/api",
            headers={"Cookie": "a=b", "Authorization": "Bearer token"},
            resource_type="XHR",
        )
    ]

    append_captures(str(out), records)
    loaded = load_captures(str(out))

    assert len(loaded) == 1
    assert loaded[0].request_id == "1"
    assert loaded[0].headers["Cookie"] == "a=b"
