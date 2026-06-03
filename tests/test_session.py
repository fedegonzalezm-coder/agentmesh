import json
from pathlib import Path

import pytest

from agentmesh.session import SessionStore


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    return SessionStore(tmp_path / "sessions")


def test_load_empty(store: SessionStore) -> None:
    assert store.load("permissions") == []


def test_save_and_load(store: SessionStore) -> None:
    messages = [
        {"role": "user", "content": "What is X?"},
        {"role": "assistant", "content": "X is Y."},
    ]
    store.save("permissions", messages)
    loaded = store.load("permissions")
    assert loaded == messages


def test_save_writes_metadata(store: SessionStore, tmp_path: Path) -> None:
    store.save("db", [{"role": "user", "content": "hello"}])
    raw = json.loads((tmp_path / "sessions" / "db.json").read_text())
    assert "last_used" in raw
    assert "created_at" in raw


def test_seed(store: SessionStore) -> None:
    messages = store.seed("ACL is managed via Bouncer.")
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert "ACL is managed via Bouncer." in messages[0]["content"]
    assert messages[1]["role"] == "assistant"


def test_list_domains_empty(store: SessionStore) -> None:
    assert store.list_domains() == []


def test_list_domains(store: SessionStore) -> None:
    store.save("permissions", [{"role": "user", "content": "hi"}])
    store.save("database", [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "ok"}])
    domains = store.list_domains()
    names = [d.domain for d in domains]
    assert "permissions" in names
    assert "database" in names
    db_info = next(d for d in domains if d.domain == "database")
    assert db_info.message_count == 2


def test_clear(store: SessionStore) -> None:
    store.save("permissions", [{"role": "user", "content": "hi"}])
    assert store.clear("permissions") is True
    assert store.load("permissions") == []
    assert store.clear("permissions") is False


def test_domain_sanitization(store: SessionStore, tmp_path: Path) -> None:
    # "../evil" → replace ".." with "" → "/evil" → replace "/" with "_" → "_evil"
    store.save("../evil", [{"role": "user", "content": "x"}])
    path = tmp_path / "sessions" / "_evil.json"
    assert path.exists()
