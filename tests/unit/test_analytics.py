"""Tests for :mod:`rewind.analytics`."""

from __future__ import annotations

from rewind.analytics import compute_insights
from rewind.analytics.insights import (
    hottest_tool,
    sort_tools_by_waste,
    top_n_tools,
    total_calls,
    waste_distribution,
)
from rewind.config import Config
from rewind.sessions import SessionManager
from rewind.store.db import open_event_store
from rewind.store.models import Event, EventKind, Session, ToolStatus


def _seed(config: Config, manager: SessionManager) -> None:
    store, _blobs = manager.open_session("s1")
    store.upsert_session(Session(id="s1", started_at=0, cwd="/x"))
    for seq, kind, tool, status in [
        (1, EventKind.SESSION_START, None, None),
        (2, EventKind.USER_PROMPT, None, None),
        (3, EventKind.POST_TOOL, "Edit", ToolStatus.PRODUCTIVE),
        (4, EventKind.POST_TOOL, "Bash", ToolStatus.WASTED),
        (5, EventKind.POST_TOOL, "Read", ToolStatus.NEUTRAL),
        (6, EventKind.POST_TOOL, "Edit", ToolStatus.PRODUCTIVE),
    ]:
        store.insert_event(
            Event(
                session_id="s1",
                seq=seq,
                ts=seq,
                kind=kind,
                tool_name=tool,
                tool_status=status,
            )
        )
    store.close()


def test_compute_insights_aggregates(config: Config, manager: SessionManager) -> None:
    _seed(config, manager)
    paths = manager.session_paths("s1")
    with open_event_store(paths.db) as store:
        insights = compute_insights(store, "s1")
    assert insights is not None
    assert insights.event_count == 6
    assert insights.user_prompt_count == 1
    assert insights.post_tool_count == 4
    assert insights.productive_count == 2
    assert insights.wasted_count == 1
    assert insights.neutral_count == 1


def test_compute_insights_returns_none_for_missing_session(
    config: Config, manager: SessionManager
) -> None:
    store, _blobs = manager.open_session("s1")
    store.close()
    paths = manager.session_paths("s1")
    with open_event_store(paths.db) as store:
        assert compute_insights(store, "absent") is None


def test_pct_helpers_handle_zero(config: Config, manager: SessionManager) -> None:
    store, _blobs = manager.open_session("empty")
    store.upsert_session(Session(id="empty", started_at=0, cwd="/x"))
    store.close()
    paths = manager.session_paths("empty")
    with open_event_store(paths.db) as store:
        insights = compute_insights(store, "empty")
    assert insights is not None
    assert insights.productive_pct == 0.0
    assert insights.waste_pct == 0.0


def test_tool_breakdown_sorted_by_calls(config: Config, manager: SessionManager) -> None:
    _seed(config, manager)
    paths = manager.session_paths("s1")
    with open_event_store(paths.db) as store:
        insights = compute_insights(store, "s1")
    assert insights is not None
    names = [t.tool_name for t in insights.tool_breakdown]
    assert names[0] == "Edit"


def test_tool_breakdown_helpers(config: Config, manager: SessionManager) -> None:
    _seed(config, manager)
    paths = manager.session_paths("s1")
    with open_event_store(paths.db) as store:
        insights = compute_insights(store, "s1")
    assert insights is not None
    assert total_calls(insights.tool_breakdown) == 4
    assert hottest_tool(insights.tool_breakdown) is not None
    assert hottest_tool([]) is None
    by_waste = sort_tools_by_waste(insights.tool_breakdown)
    assert by_waste[0].wasted >= by_waste[-1].wasted
    assert top_n_tools(insights.tool_breakdown, 1)[0].tool_name == "Edit"
    assert top_n_tools(insights.tool_breakdown, 0) == []


def test_waste_distribution(config: Config, manager: SessionManager) -> None:
    _seed(config, manager)
    paths = manager.session_paths("s1")
    with open_event_store(paths.db) as store:
        insights = compute_insights(store, "s1")
        events = store.list_events("s1")
    assert insights is not None
    counter = waste_distribution(events)
    assert counter["Bash"] == 1
