"""Tests for the SessionManager façade."""

from __future__ import annotations

from rewind.capture.hooks import ingest_payload
from rewind.capture.payload import parse_payload
from rewind.config import Config
from rewind.sessions import SessionManager


def test_open_session_creates_dirs(config: Config) -> None:
    manager = SessionManager(config)
    store, blobs = manager.open_session("s1")
    try:
        assert manager.session_paths("s1").root.is_dir()
        assert manager.session_paths("s1").db.exists()
        assert blobs.blobs_dir.is_dir()
    finally:
        store.close()


def test_set_get_clear_current_session(config: Config) -> None:
    manager = SessionManager(config)
    assert manager.get_current_session() is None
    manager.set_current_session("s1")
    assert manager.get_current_session() == "s1"
    manager.clear_current_session()
    assert manager.get_current_session() is None


def test_list_sessions_returns_empty_initially(config: Config) -> None:
    manager = SessionManager(config)
    assert manager.list_sessions() == []


def test_list_sessions_returns_in_recent_first(config: Config, monkeypatch: object) -> None:
    _ = monkeypatch
    manager = SessionManager(config)
    older = parse_payload(
        {
            "session_id": "older",
            "transcript_path": None,
            "cwd": "/x",
            "permission_mode": "default",
            "hook_event_name": "SessionStart",
            "source": "startup",
        }
    )
    ingest_payload(payload=older, config=config, manager=manager, now_ms=100)
    newer = parse_payload(
        {
            "session_id": "newer",
            "transcript_path": None,
            "cwd": "/x",
            "permission_mode": "default",
            "hook_event_name": "SessionStart",
            "source": "startup",
        }
    )
    ingest_payload(payload=newer, config=config, manager=manager, now_ms=200)
    sessions = manager.list_sessions()
    assert [s.id for s in sessions] == ["newer", "older"]


def test_delete_session_removes_dir(config: Config) -> None:
    manager = SessionManager(config)
    store, _blobs = manager.open_session("doomed")
    store.close()
    assert manager.has_session("doomed")
    assert manager.delete_session("doomed") is True
    assert not manager.session_paths("doomed").root.exists()


def test_delete_session_returns_false_for_missing(config: Config) -> None:
    manager = SessionManager(config)
    assert manager.delete_session("nope") is False


def test_session_paths_use_session_id_as_dir(config: Config) -> None:
    manager = SessionManager(config)
    paths = manager.session_paths("abc")
    assert paths.root == config.sessions_dir / "abc"


def test_latest_session_when_empty(config: Config) -> None:
    manager = SessionManager(config)
    assert manager.latest_session() is None
