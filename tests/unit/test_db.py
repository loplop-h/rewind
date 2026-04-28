"""Tests for the SQLite-backed event store."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from rewind.store.db import (
    SCHEMA_VERSION,
    EventStore,
    open_event_store,
)
from rewind.store.models import (
    Event,
    EventKind,
    FileSnapshot,
    Session,
    ToolStatus,
)


@pytest.fixture()
def store(tmp_path: Path) -> EventStore:
    return open_event_store(tmp_path / "events.db")


def test_schema_is_at_target_version(store: EventStore) -> None:
    row = store.connection.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    assert row["v"] == SCHEMA_VERSION


def test_open_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "events.db"
    open_event_store(db_path).close()
    store = open_event_store(db_path)
    row = store.connection.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    assert row["v"] == SCHEMA_VERSION
    store.close()


def test_session_round_trip(store: EventStore) -> None:
    session = Session(id="s1", started_at=1000, cwd="/work")
    store.upsert_session(session)
    fetched = store.get_session("s1")
    assert fetched is not None
    assert fetched.id == "s1"
    assert fetched.cwd == "/work"
    assert fetched.ended_at is None


def test_session_upsert_keeps_unspecified_fields(store: EventStore) -> None:
    initial = Session(id="s1", started_at=1, cwd="/x", model="opus")
    store.upsert_session(initial)
    update = Session(id="s1", started_at=1, cwd="/x", ended_at=99)
    store.upsert_session(update)
    after = store.get_session("s1")
    assert after is not None
    assert after.ended_at == 99
    assert after.model == "opus"


def test_event_round_trip_with_seq(store: EventStore) -> None:
    store.upsert_session(Session(id="s1", started_at=0, cwd="/x"))
    seq = store.next_seq("s1")
    assert seq == 1
    ev = Event(session_id="s1", seq=seq, ts=1, kind=EventKind.SESSION_START)
    new_id = store.insert_event(ev)
    assert new_id > 0
    assert store.next_seq("s1") == 2
    fetched = store.get_event(new_id)
    assert fetched is not None
    assert fetched.kind is EventKind.SESSION_START


def test_get_event_by_seq(store: EventStore) -> None:
    store.upsert_session(Session(id="s1", started_at=0, cwd="/x"))
    store.insert_event(
        Event(session_id="s1", seq=1, ts=1, kind=EventKind.USER_PROMPT, tool_name=None)
    )
    store.insert_event(
        Event(
            session_id="s1",
            seq=2,
            ts=2,
            kind=EventKind.PRE_TOOL,
            tool_name="Edit",
        )
    )
    ev = store.get_event_by_seq("s1", 2)
    assert ev is not None
    assert ev.tool_name == "Edit"


def test_list_events_in_seq_order(store: EventStore) -> None:
    store.upsert_session(Session(id="s1", started_at=0, cwd="/x"))
    store.insert_event(Event(session_id="s1", seq=2, ts=2, kind=EventKind.PRE_TOOL))
    store.insert_event(Event(session_id="s1", seq=1, ts=1, kind=EventKind.USER_PROMPT))
    seqs = [ev.seq for ev in store.list_events("s1")]
    assert seqs == [1, 2]


def test_unique_seq_per_session(store: EventStore) -> None:
    store.upsert_session(Session(id="s1", started_at=0, cwd="/x"))
    store.insert_event(Event(session_id="s1", seq=1, ts=1, kind=EventKind.USER_PROMPT))
    with pytest.raises(sqlite3.IntegrityError):
        store.insert_event(Event(session_id="s1", seq=1, ts=2, kind=EventKind.USER_PROMPT))


def test_snapshots_round_trip_and_join(store: EventStore) -> None:
    store.upsert_session(Session(id="s1", started_at=0, cwd="/x"))
    e1 = store.insert_event(
        Event(session_id="s1", seq=1, ts=1, kind=EventKind.PRE_TOOL, tool_name="Edit")
    )
    e2 = store.insert_event(
        Event(session_id="s1", seq=2, ts=2, kind=EventKind.PRE_TOOL, tool_name="Edit")
    )
    store.insert_file_snapshot(
        FileSnapshot(event_id=e1, path="/x/a", before_hash="0" * 64, after_hash=None)
    )
    store.insert_file_snapshot(
        FileSnapshot(event_id=e2, path="/x/a", before_hash="1" * 64, after_hash="2" * 64)
    )
    pairs = store.list_snapshots_up_to_seq("s1", seq_exclusive=3)
    assert len(pairs) == 2
    pre_seqs = [ev.seq for ev, _snap in pairs]
    assert pre_seqs == [1, 2]


def test_session_summary_handles_classifications(store: EventStore) -> None:
    store.upsert_session(Session(id="s1", started_at=0, cwd="/x"))
    store.insert_event(
        Event(
            session_id="s1",
            seq=1,
            ts=1,
            kind=EventKind.POST_TOOL,
            tool_name="Edit",
            tool_status=ToolStatus.PRODUCTIVE,
        )
    )
    store.insert_event(
        Event(
            session_id="s1",
            seq=2,
            ts=2,
            kind=EventKind.POST_TOOL,
            tool_name="Bash",
            tool_status=ToolStatus.WASTED,
        )
    )
    summary = store.session_summary("s1")
    assert summary is not None
    assert summary.event_count == 2
    assert summary.productive_pct == 50.0
    assert summary.wasted_pct == 50.0


def test_session_summary_returns_none_for_missing(store: EventStore) -> None:
    assert store.session_summary("nope") is None


def test_get_session_returns_none_for_missing(store: EventStore) -> None:
    assert store.get_session("nope") is None
