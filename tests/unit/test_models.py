"""Tests for the dataclass models in :mod:`rewind.store.models`."""

from __future__ import annotations

import pytest

from rewind.store.models import (
    Event,
    EventKind,
    FileSnapshot,
    Session,
    SessionSummary,
    ToolStatus,
)


def test_event_kind_from_str_round_trip() -> None:
    for kind in EventKind:
        assert EventKind.from_str(kind.value) is kind


def test_event_kind_rejects_unknown() -> None:
    with pytest.raises(ValueError) as exc:
        EventKind.from_str("nope")
    assert "valid" in str(exc.value)


def test_session_defaults_are_safe() -> None:
    session = Session(id="s1", started_at=1, cwd="/x")
    assert session.total_cost_usd == 0.0
    assert session.total_events == 0
    assert session.exit_reason is None


def test_event_carries_classification() -> None:
    event = Event(
        session_id="s1",
        seq=1,
        ts=1,
        kind=EventKind.POST_TOOL,
        tool_name="Write",
        tool_status=ToolStatus.PRODUCTIVE,
    )
    assert event.tool_status is ToolStatus.PRODUCTIVE


def test_file_snapshot_allows_double_none() -> None:
    """A pre-only snapshot for a not-yet-existing file legitimately has both None."""

    snap = FileSnapshot(event_id=1, path="/x", before_hash=None, after_hash=None)
    assert snap.path == "/x"
    assert snap.before_hash is None and snap.after_hash is None


def test_session_summary_defaults() -> None:
    summary = SessionSummary(
        session=Session(id="s1", started_at=1, cwd="/x"),
        event_count=0,
        file_count=0,
    )
    assert summary.productive_pct == 0.0
    assert summary.wasted_pct == 0.0
