"""Hook handlers: high-level orchestration of payload → events + snapshots."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from rewind.capture.payload import (
    HookPayload,
    PostToolPayload,
    PreToolPayload,
    SessionEndPayload,
    SessionStartPayload,
    UserPromptPayload,
    parse_payload,
)
from rewind.capture.snapshot import (
    classify_tool_call,
    record_post_tool_snapshot,
    record_pre_tool_snapshot,
)
from rewind.config import DEFAULT_TOOL_OUTPUT_TRUNCATE_BYTES, Config
from rewind.sessions import SessionManager
from rewind.store.models import Event, EventKind, Session, ToolStatus

_TRUNCATION_MARKER = "...rewind:truncated..."


@dataclass(frozen=True, slots=True)
class HookResult:
    """Outcome of a hook ingest. Used by tests and by the CLI for exit codes."""

    session_id: str
    event_id: int
    seq: int
    snapshot_count: int


class HookHandler:
    """Stateless façade around :func:`ingest_payload` that holds shared deps."""

    def __init__(self, config: Config | None = None) -> None:
        self._config = config or Config.load()
        self._manager = SessionManager(self._config)

    def handle(self, payload: HookPayload) -> HookResult:
        return ingest_payload(payload=payload, config=self._config, manager=self._manager)


def ingest_payload(
    *,
    payload: HookPayload,
    config: Config,
    manager: SessionManager,
    now_ms: int | None = None,
    truncate_bytes: int = DEFAULT_TOOL_OUTPUT_TRUNCATE_BYTES,
) -> HookResult:
    """Persist a single hook payload as an event (and snapshots if applicable)."""

    if config.capture_disabled:
        return HookResult(session_id=payload.session_id, event_id=0, seq=0, snapshot_count=0)
    timestamp = now_ms if now_ms is not None else int(time.time() * 1000)
    store, blobs = manager.open_session(payload.session_id)
    try:
        manager.set_current_session(payload.session_id)
        if isinstance(payload, SessionStartPayload):
            session = _session_from_start(payload, started_at=timestamp)
            store.upsert_session(session)
            event = _build_event(
                session_id=payload.session_id,
                seq=store.next_seq(payload.session_id),
                ts=timestamp,
                kind=EventKind.SESSION_START,
                model=payload.model,
            )
            event_id = store.insert_event(event)
            return HookResult(
                session_id=payload.session_id,
                event_id=event_id,
                seq=event.seq,
                snapshot_count=0,
            )
        _ensure_session(payload, store, manager, started_at=timestamp)
        if isinstance(payload, UserPromptPayload):
            event = _build_event(
                session_id=payload.session_id,
                seq=store.next_seq(payload.session_id),
                ts=timestamp,
                kind=EventKind.USER_PROMPT,
                tool_input_json=_truncate(json.dumps({"prompt": payload.prompt}), truncate_bytes),
            )
            event_id = store.insert_event(event)
            return HookResult(
                session_id=payload.session_id,
                event_id=event_id,
                seq=event.seq,
                snapshot_count=0,
            )
        if isinstance(payload, PreToolPayload):
            event = _build_event(
                session_id=payload.session_id,
                seq=store.next_seq(payload.session_id),
                ts=timestamp,
                kind=EventKind.PRE_TOOL,
                tool_name=payload.tool_name,
                tool_input_json=_truncate(json.dumps(payload.tool_input), truncate_bytes),
            )
            event_id = store.insert_event(event)
            snaps = record_pre_tool_snapshot(
                store=store,
                blobs=blobs,
                event_id=event_id,
                tool_name=payload.tool_name,
                tool_input=payload.tool_input,
            )
            return HookResult(
                session_id=payload.session_id,
                event_id=event_id,
                seq=event.seq,
                snapshot_count=len(snaps),
            )
        if isinstance(payload, PostToolPayload):
            status = classify_tool_call(payload.tool_name, payload.tool_response)
            pre_event = _find_matching_pre_event(
                store, payload.session_id, payload.tool_name, payload.tool_input
            )
            event = _build_event(
                session_id=payload.session_id,
                seq=store.next_seq(payload.session_id),
                ts=timestamp,
                kind=EventKind.POST_TOOL,
                tool_name=payload.tool_name,
                tool_input_json=_truncate(json.dumps(payload.tool_input), truncate_bytes),
                tool_output_json=_truncate(json.dumps(payload.tool_response), truncate_bytes),
                tool_status=status.value,
                duration_ms=payload.duration_ms,
            )
            event_id = store.insert_event(event)
            snaps = record_post_tool_snapshot(
                store=store,
                blobs=blobs,
                pre_event_id=pre_event.id if pre_event is not None else None,
                post_event_id=event_id,
                tool_name=payload.tool_name,
                tool_input=payload.tool_input,
            )
            return HookResult(
                session_id=payload.session_id,
                event_id=event_id,
                seq=event.seq,
                snapshot_count=len(snaps),
            )
        if isinstance(payload, SessionEndPayload):
            existing = store.get_session(payload.session_id)
            updated = _update_session_end(existing, payload, ended_at=timestamp)
            store.upsert_session(updated)
            event = _build_event(
                session_id=payload.session_id,
                seq=store.next_seq(payload.session_id),
                ts=timestamp,
                kind=EventKind.SESSION_END,
                tool_input_json=_truncate(
                    json.dumps(
                        {
                            "exit_reason": payload.exit_reason,
                            "total_cost_usd": payload.total_cost_usd,
                            "total_tokens_in": payload.total_tokens_in,
                            "total_tokens_out": payload.total_tokens_out,
                            "total_events": payload.total_events,
                        }
                    ),
                    truncate_bytes,
                ),
            )
            event_id = store.insert_event(event)
            manager.clear_current_session()
            return HookResult(
                session_id=payload.session_id,
                event_id=event_id,
                seq=event.seq,
                snapshot_count=0,
            )
        raise ValueError(f"unhandled payload type: {type(payload).__name__}")
    finally:
        store.close()


def ingest_raw(
    *,
    raw: str | dict[str, Any],
    config: Config,
    manager: SessionManager,
    now_ms: int | None = None,
) -> HookResult:
    """Convenience: parse + ingest a raw stdin payload."""

    payload = parse_payload(raw)
    return ingest_payload(payload=payload, config=config, manager=manager, now_ms=now_ms)


def _session_from_start(payload: SessionStartPayload, *, started_at: int) -> Session:
    return Session(
        id=payload.session_id,
        started_at=started_at,
        cwd=payload.cwd,
        model=payload.model,
    )


def _ensure_session(
    payload: HookPayload,
    store: Any,
    manager: SessionManager,
    *,
    started_at: int,
) -> None:
    """If a hook fires without a prior SessionStart, create a stub session."""

    if store.get_session(payload.session_id) is not None:
        return
    stub = Session(
        id=payload.session_id,
        started_at=started_at,
        cwd=payload.cwd,
    )
    store.upsert_session(stub)
    manager.set_current_session(payload.session_id)


def _update_session_end(
    existing: Session | None,
    payload: SessionEndPayload,
    *,
    ended_at: int,
) -> Session:
    base = existing or Session(
        id=payload.session_id,
        started_at=ended_at,
        cwd=payload.cwd,
    )
    return Session(
        id=base.id,
        started_at=base.started_at,
        ended_at=ended_at,
        cwd=base.cwd,
        model=base.model,
        total_cost_usd=payload.total_cost_usd or base.total_cost_usd,
        total_tokens_in=payload.total_tokens_in or base.total_tokens_in,
        total_tokens_out=payload.total_tokens_out or base.total_tokens_out,
        total_events=payload.total_events or base.total_events,
        exit_reason=payload.exit_reason or base.exit_reason,
    )


def _build_event(
    *,
    session_id: str,
    seq: int,
    ts: int,
    kind: EventKind,
    tool_name: str | None = None,
    tool_input_json: str | None = None,
    tool_output_json: str | None = None,
    tool_status: str | None = None,
    duration_ms: int | None = None,
    model: str | None = None,
) -> Event:
    status = ToolStatus(tool_status) if tool_status else None
    return Event(
        session_id=session_id,
        seq=seq,
        ts=ts,
        kind=kind,
        tool_name=tool_name,
        tool_input_json=tool_input_json,
        tool_output_json=tool_output_json,
        tool_status=status,
        duration_ms=duration_ms,
        model=model,
    )


def _truncate(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    keep = max(0, max_bytes - len(_TRUNCATION_MARKER.encode("utf-8")))
    return encoded[:keep].decode("utf-8", errors="replace") + _TRUNCATION_MARKER


def _find_matching_pre_event(
    store: Any,
    session_id: str,
    tool_name: str,
    tool_input: dict[str, Any],
) -> Event | None:
    """Find the most recent PreToolUse event for the same tool that has no matching post yet.

    Heuristic: same session, same tool_name, kind = PRE_TOOL, with the same
    primary file path (if applicable) — and where no PostToolUse event with
    a higher seq references the same path. Used by snapshot to update the
    before/after pair atomically.
    """

    target_paths = {tool_input.get(k) for k in ("file_path", "notebook_path") if tool_input.get(k)}
    events: list[Event] = store.list_events(session_id)
    for ev in reversed(events):
        if ev.kind != EventKind.PRE_TOOL or ev.tool_name != tool_name:
            continue
        if not target_paths:
            return ev
        if ev.tool_input_json is None:
            continue
        try:
            parsed = json.loads(ev.tool_input_json)
        except json.JSONDecodeError:
            continue
        ev_paths = {parsed.get(k) for k in ("file_path", "notebook_path") if parsed.get(k)}
        if ev_paths == target_paths:
            return ev
    return None
