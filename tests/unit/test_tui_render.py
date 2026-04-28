"""Tests for the TUI renderer (non-interactive)."""

from __future__ import annotations

from rewind.config import Config
from rewind.sessions import SessionManager
from rewind.store.blob import BlobStore
from rewind.store.db import open_event_store
from rewind.store.models import Event, EventKind, Session, ToolStatus
from rewind.tui import build_timeline_table, build_unified_diff
from rewind.tui.app import render_event_detail, render_session, run_tui
from rewind.tui.diff import safe_decode


def _seed_session_for_render(
    config: Config, manager: SessionManager, *, with_post: bool = True
) -> str:
    store, _blobs = manager.open_session("s1")
    store.upsert_session(Session(id="s1", started_at=0, cwd="/x"))
    store.insert_event(Event(session_id="s1", seq=1, ts=1, kind=EventKind.SESSION_START))
    store.insert_event(
        Event(
            session_id="s1",
            seq=2,
            ts=2,
            kind=EventKind.USER_PROMPT,
            tool_input_json='{"prompt":"hi"}',
        )
    )
    if with_post:
        store.insert_event(
            Event(
                session_id="s1",
                seq=3,
                ts=3,
                kind=EventKind.POST_TOOL,
                tool_name="Edit",
                tool_status=ToolStatus.PRODUCTIVE,
                tool_input_json='{"file_path":"/x/a.py"}',
                tool_output_json='{"success":true}',
            )
        )
    store.close()
    return "s1"


def test_build_timeline_table_runs() -> None:
    events = [
        Event(session_id="s1", seq=1, ts=1, kind=EventKind.SESSION_START),
        Event(
            session_id="s1",
            seq=2,
            ts=2,
            kind=EventKind.USER_PROMPT,
            tool_input_json='{"prompt":"hello"}',
        ),
        Event(
            session_id="s1",
            seq=3,
            ts=3,
            kind=EventKind.POST_TOOL,
            tool_name="Bash",
            tool_status=ToolStatus.WASTED,
            tool_input_json='{"command":"echo"}',
        ),
    ]
    table = build_timeline_table(events, title="t")
    assert table.row_count == 3


def test_render_session_returns_text(config: Config, manager: SessionManager) -> None:
    _seed_session_for_render(config, manager)
    paths = manager.session_paths("s1")
    with open_event_store(paths.db) as store:
        events = store.list_events("s1")
    out = render_session(events=events, title="t")
    assert "session_start" in out
    assert "user_prompt" in out


def test_run_tui_no_sessions(config: Config, capsys: object) -> None:
    rc = run_tui(config=config, session_id=None)
    assert rc == 1


def test_run_tui_session_not_found(config: Config) -> None:
    rc = run_tui(config=config, session_id="missing")
    assert rc == 2


def test_run_tui_full_flow(config: Config, manager: SessionManager, capsys: object) -> None:
    _seed_session_for_render(config, manager)
    rc = run_tui(config=config, session_id="s1")
    assert rc == 0
    rc = run_tui(config=config, session_id="s1", seq=2)
    assert rc == 0


def test_run_tui_seq_not_found(config: Config, manager: SessionManager) -> None:
    _seed_session_for_render(config, manager, with_post=False)
    rc = run_tui(config=config, session_id="s1", seq=999)
    assert rc == 3


def test_unified_diff_renders() -> None:
    out = build_unified_diff(
        before_text="a\n",
        after_text="b\n",
        path="x",
    )
    assert "x" in str(out)


def test_safe_decode_handles_invalid_bytes() -> None:
    assert safe_decode(b"\xff\xfe") is not None


def test_render_event_detail(config: Config, manager: SessionManager) -> None:
    _seed_session_for_render(config, manager)
    paths = manager.session_paths("s1")
    with open_event_store(paths.db) as store:
        ev = store.get_event_by_seq("s1", 3)
    assert ev is not None
    blobs = BlobStore(paths.root)
    blobs.ensure_dirs()
    out = render_event_detail(event=ev, snapshots=[], blobs=blobs)
    assert "post_tool" in out or "Edit" in out
