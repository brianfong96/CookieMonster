import pytest
from cryptography.fernet import Fernet

from cookie_monster.models import CapturedRequest
from cookie_monster.storage import append_captures, load_captures


def test_storage_roundtrip_encrypted(tmp_path):
    key = Fernet.generate_key().decode("utf-8")
    out = tmp_path / "captures.enc.jsonl"
    records = [
        CapturedRequest(
            request_id="1",
            method="GET",
            url="https://example.com/api",
            headers={"Cookie": "a=b"},
        )
    ]
    append_captures(str(out), records, encryption_key=key)

    raw = out.read_text(encoding="utf-8")
    assert raw.startswith("ENC:")

    loaded = load_captures(str(out), encryption_key=key)
    assert len(loaded) == 1
    assert loaded[0].headers["Cookie"] == "a=b"


def test_storage_encrypted_requires_key(tmp_path):
    key = Fernet.generate_key().decode("utf-8")
    out = tmp_path / "captures.enc.jsonl"
    append_captures(
        str(out),
        [CapturedRequest(request_id="1", method="GET", url="https://example.com", headers={"Cookie": "x"})],
        encryption_key=key,
    )
    with pytest.raises(RuntimeError):
        load_captures(str(out))
