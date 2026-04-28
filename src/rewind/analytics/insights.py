"""Compute summary insights for a captured session.

These shapes drive both the ``rewind stats`` CLI and the (later) TUI insights
panel. They are intentionally JSON-serialisable so we can stream them to the
export renderer without a separate model.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from rewind.store.db import EventStore
from rewind.store.models import Event, EventKind, Session, ToolStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolBreakdown:
    """Aggregate per-tool stats."""

    tool_name: str
    calls: int
    productive: int
    wasted: int
    neutral: int

    @property
    def waste_pct(self) -> float:
        return (self.wasted / self.calls * 100) if self.calls else 0.0


@dataclass(frozen=True, slots=True, kw_only=True)
class SessionInsights:
    """All the numbers we surface for a single session."""

    session: Session
    event_count: int
    user_prompt_count: int
    pre_tool_count: int
    post_tool_count: int
    productive_count: int
    wasted_count: int
    neutral_count: int
    files_touched: int
    tool_breakdown: list[ToolBreakdown]

    @property
    def waste_pct(self) -> float:
        classified = self.productive_count + self.wasted_count + self.neutral_count
        if classified == 0:
            return 0.0
        return (self.wasted_count / classified) * 100

    @property
    def productive_pct(self) -> float:
        classified = self.productive_count + self.wasted_count + self.neutral_count
        if classified == 0:
            return 0.0
        return (self.productive_count / classified) * 100


def compute_insights(store: EventStore, session_id: str) -> SessionInsights | None:
    """Build a :class:`SessionInsights` from the event store, or None if missing."""

    session = store.get_session(session_id)
    if session is None:
        return None
    events = store.list_events(session_id)
    return _summarise(session=session, events=events, store=store)


def _summarise(
    *,
    session: Session,
    events: Iterable[Event],
    store: EventStore,
) -> SessionInsights:
    user_prompts = 0
    pre_tools = 0
    post_tools = 0
    productive = 0
    wasted = 0
    neutral = 0
    per_tool: dict[str, dict[str, int]] = {}
    file_paths: set[str] = set()
    total_events = 0

    for ev in events:
        total_events += 1
        if ev.kind is EventKind.USER_PROMPT:
            user_prompts += 1
        elif ev.kind is EventKind.PRE_TOOL:
            pre_tools += 1
        elif ev.kind is EventKind.POST_TOOL:
            post_tools += 1
            tool = ev.tool_name or "unknown"
            counts = per_tool.setdefault(
                tool, {"calls": 0, "productive": 0, "wasted": 0, "neutral": 0}
            )
            counts["calls"] += 1
            if ev.tool_status is ToolStatus.PRODUCTIVE:
                productive += 1
                counts["productive"] += 1
            elif ev.tool_status is ToolStatus.WASTED:
                wasted += 1
                counts["wasted"] += 1
            else:
                neutral += 1
                counts["neutral"] += 1
        if ev.id is not None:
            for snap in store.list_snapshots(ev.id):
                file_paths.add(snap.path)

    tool_breakdown = sorted(
        (
            ToolBreakdown(
                tool_name=name,
                calls=counts["calls"],
                productive=counts["productive"],
                wasted=counts["wasted"],
                neutral=counts["neutral"],
            )
            for name, counts in per_tool.items()
        ),
        key=lambda b: b.calls,
        reverse=True,
    )
    return SessionInsights(
        session=session,
        event_count=total_events,
        user_prompt_count=user_prompts,
        pre_tool_count=pre_tools,
        post_tool_count=post_tools,
        productive_count=productive,
        wasted_count=wasted,
        neutral_count=neutral,
        files_touched=len(file_paths),
        tool_breakdown=tool_breakdown,
    )


def sort_tools_by_waste(breakdown: Iterable[ToolBreakdown]) -> list[ToolBreakdown]:
    """Helper for callers that want the messiest tools first."""

    return sorted(breakdown, key=lambda b: (b.wasted, b.calls), reverse=True)


def top_n_tools(breakdown: Iterable[ToolBreakdown], n: int) -> list[ToolBreakdown]:
    return list(breakdown)[: max(0, n)]


def total_calls(breakdown: Iterable[ToolBreakdown]) -> int:
    return sum(b.calls for b in breakdown)


def hottest_tool(breakdown: Iterable[ToolBreakdown]) -> ToolBreakdown | None:
    items = list(breakdown)
    return items[0] if items else None


def waste_distribution(events: Iterable[Event]) -> Counter[str]:
    """How many wasted calls per tool. Useful for histograms."""

    counter: Counter[str] = Counter()
    for ev in events:
        if ev.kind is EventKind.POST_TOOL and ev.tool_status is ToolStatus.WASTED:
            counter[ev.tool_name or "unknown"] += 1
    return counter
