from pathlib import Path

from roomba.store import Store


def test_credentials_roundtrip(tmp_path: Path):
    store = Store(tmp_path / "config.json")
    store.set_credentials("user@example.com", "s3cret-ñ")
    assert store.email == "user@example.com"
    assert store.password == "s3cret-ñ"


def test_password_not_stored_in_plaintext(tmp_path: Path):
    path = tmp_path / "config.json"
    Store(path).set_credentials("user@example.com", "s3cret")
    assert "s3cret" not in path.read_text()


def test_session_cache_expiry(tmp_path: Path):
    store = Store(tmp_path / "config.json")
    store.save_session({"iot_token": "old"})
    store.data["session"]["_at"] = 0
    store.save()
    assert store.cached_session() is None


def test_forget_all(tmp_path: Path):
    store = Store(tmp_path / "config.json")
    store.set_credentials("a@b.c", "pw")
    store.forget_all()
    assert store.email is None
    assert store.password is None
