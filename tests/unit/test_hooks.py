"""Tests for the hook ingestion pipeline."""

from __future__ import annotations

from pathlib import Path

from rewind.capture.hooks import HookHandler, ingest_payload, ingest_raw
from rewind.capture.payload import parse_payload
from rewind.config import Config
from rewind.sessions import SessionManager
from rewind.store.db import open_event_store
from rewind.store.models import EventKind, ToolStatus


def _ingest(
    raw: str,
    *,
    config: Config,
    manager: SessionManager,
    now_ms: int = 100,
) -> None:
    ingest_payload(
        payload=parse_payload(raw),
        config=config,
        manager=manager,
        now_ms=now_ms,
    )


def test_session_start_creates_session(
    config: Config, manager: SessionManager, make_payload: object
) -> None:
    raw = make_payload(  # type: ignore[operator]
        hook_event_name="SessionStart",
        source="startup",
        model="claude-opus-4-7",
    )
    _ingest(raw, config=config, manager=manager, now_ms=100)
    paths = manager.session_paths("session-abcdef123456")
    with open_event_store(paths.db) as store:
        s = store.get_session("session-abcdef123456")
        assert s is not None
        assert s.model == "claude-opus-4-7"
        events = store.list_events("session-abcdef123456")
        assert [e.kind for e in events] == [EventKind.SESSION_START]
    assert manager.get_current_session() == "session-abcdef123456"


def test_user_prompt_appends_event(
    config: Config, manager: SessionManager, make_payload: object
) -> None:
    _ingest(
        make_payload(hook_event_name="SessionStart", source="startup"),  # type: ignore[operator]
        config=config,
        manager=manager,
        now_ms=100,
    )
    _ingest(
        make_payload(  # type: ignore[operator]
            hook_event_name="UserPromptSubmit",
            prompt="write tests",
        ),
        config=config,
        manager=manager,
        now_ms=110,
    )
    paths = manager.session_paths("session-abcdef123456")
    with open_event_store(paths.db) as store:
        events = store.list_events("session-abcdef123456")
    kinds = [e.kind for e in events]
    assert kinds == [EventKind.SESSION_START, EventKind.USER_PROMPT]


def test_pre_tool_writes_snapshot_for_edit(
    config: Config,
    manager: SessionManager,
    make_payload: object,
    workspace: Path,
) -> None:
    target = workspace / "x.py"
    target.write_text("hello\n", encoding="utf-8")
    _ingest(
        make_payload(hook_event_name="SessionStart", cwd=str(workspace)),  # type: ignore[operator]
        config=config,
        manager=manager,
        now_ms=100,
    )
    _ingest(
        make_payload(  # type: ignore[operator]
            hook_event_name="PreToolUse",
            cwd=str(workspace),
            tool_name="Edit",
            tool_input={"file_path": str(target)},
        ),
        config=config,
        manager=manager,
        now_ms=110,
    )
    paths = manager.session_paths("session-abcdef123456")
    with open_event_store(paths.db) as store:
        events = store.list_events("session-abcdef123456")
        ev = next(e for e in events if e.kind is EventKind.PRE_TOOL)
        assert ev.id is not None
        snaps = store.list_snapshots(ev.id)
        assert len(snaps) == 1
        assert snaps[0].before_hash is not None
        assert snaps[0].after_hash is None


def test_post_tool_links_to_pre_event_and_classifies(
    config: Config,
    manager: SessionManager,
    make_payload: object,
    workspace: Path,
) -> None:
    target = workspace / "x.py"
    target.write_text("hello\n", encoding="utf-8")
    _ingest(
        make_payload(hook_event_name="SessionStart", cwd=str(workspace)),  # type: ignore[operator]
        config=config,
        manager=manager,
        now_ms=100,
    )
    _ingest(
        make_payload(  # type: ignore[operator]
            hook_event_name="PreToolUse",
            cwd=str(workspace),
            tool_name="Edit",
            tool_input={"file_path": str(target)},
        ),
        config=config,
        manager=manager,
        now_ms=110,
    )
    target.write_text("hello, world\n", encoding="utf-8")
    _ingest(
        make_payload(  # type: ignore[operator]
            hook_event_name="PostToolUse",
            cwd=str(workspace),
            tool_name="Edit",
            tool_input={"file_path": str(target)},
            tool_response={"success": True},
            duration_ms=12,
        ),
        config=config,
        manager=manager,
        now_ms=120,
    )
    paths = manager.session_paths("session-abcdef123456")
    with open_event_store(paths.db) as store:
        events = store.list_events("session-abcdef123456")
        post_event = next(e for e in events if e.kind is EventKind.POST_TOOL)
        assert post_event.tool_status is ToolStatus.PRODUCTIVE
        # The pre event's snapshot should now have an after_hash filled in.
        pre_event = next(e for e in events if e.kind is EventKind.PRE_TOOL)
        assert pre_event.id is not None
        snaps = store.list_snapshots(pre_event.id)
        assert snaps[0].after_hash is not None


def test_session_end_clears_current(
    config: Config, manager: SessionManager, make_payload: object
) -> None:
    _ingest(
        make_payload(hook_event_name="SessionStart"),  # type: ignore[operator]
        config=config,
        manager=manager,
        now_ms=100,
    )
    assert manager.get_current_session() == "session-abcdef123456"
    _ingest(
        make_payload(  # type: ignore[operator]
            hook_event_name="Stop",
            exit_reason="normal",
            total_cost_usd=0.42,
        ),
        config=config,
        manager=manager,
        now_ms=200,
    )
    assert manager.get_current_session() is None
    paths = manager.session_paths("session-abcdef123456")
    with open_event_store(paths.db) as store:
        s = store.get_session("session-abcdef123456")
    assert s is not None
    assert s.ended_at == 200
    assert s.total_cost_usd == 0.42


def test_capture_disabled_short_circuits(
    rewind_home: Path, manager: SessionManager, make_payload: object
) -> None:
    cfg_path = rewind_home / "config.toml"
    cfg_path.write_text("capture_disabled = true\n", encoding="utf-8")
    config = Config.load()
    raw = make_payload(hook_event_name="SessionStart")  # type: ignore[operator]
    payload = parse_payload(raw)
    result = ingest_payload(
        payload=payload,
        config=config,
        manager=manager,
        now_ms=10,
    )
    assert result.event_id == 0
    assert manager.list_sessions() == []


def test_ingest_raw_dispatches(
    config: Config,
    manager: SessionManager,
    make_payload: object,
) -> None:
    raw = make_payload(hook_event_name="SessionStart")  # type: ignore[operator]
    result = ingest_raw(raw=raw, config=config, manager=manager, now_ms=99)
    assert result.seq == 1


def test_handler_facade(config: Config, make_payload: object) -> None:
    handler = HookHandler(config=config)
    payload = parse_payload(make_payload(hook_event_name="SessionStart"))  # type: ignore[operator]
    result = handler.handle(payload)
    assert result.session_id == "session-abcdef123456"
