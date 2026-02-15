from __future__ import annotations

import os

import pytest

from cookie_monster.crypto import load_or_create_key


@pytest.mark.skipif(os.name == "nt", reason="POSIX file mode assertion")
def test_load_or_create_key_sets_private_permissions(tmp_path):
    key_path = tmp_path / "key.txt"
    _ = load_or_create_key(str(key_path))
    mode = key_path.stat().st_mode & 0o777
    assert mode == 0o600
