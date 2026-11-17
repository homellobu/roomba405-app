import pytest

from roomba.cli import resolve_blid
from roomba.store import Store


def make_store(tmp_path):
    return Store(tmp_path / "config.json")


def test_prefers_explicit_blid_and_remembers_it(tmp_path):
    store = make_store(tmp_path)
    session = {"robots": {"A": {"name": "Uno"}, "B": {"name": "Dos"}}}
    assert resolve_blid(store, session, prefer_blid="B") == "B"
    assert store.blid == "B"


def test_rejects_unknown_blid(tmp_path):
    store = make_store(tmp_path)
    session = {"robots": {"A": {}}}
    with pytest.raises(RuntimeError, match="no está"):
        resolve_blid(store, session, prefer_blid="X")


def test_reuses_stored_blid(tmp_path):
    store = make_store(tmp_path)
    store.set_blid("A")
    session = {"robots": {"A": {}, "B": {}}}
    assert resolve_blid(store, session) == "A"


def test_single_robot_auto_selected(tmp_path):
    store = make_store(tmp_path)
    session = {"robots": {"A": {}}}
    assert resolve_blid(store, session) == "A"
    assert store.blid == "A"


def test_multiple_robots_without_picker_returns_none(tmp_path):
    store = make_store(tmp_path)
    session = {"robots": {"A": {}, "B": {}}}
    assert resolve_blid(store, session) is None
