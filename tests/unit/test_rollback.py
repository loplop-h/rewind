"""Tests for the rollback engine and safety checks."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from rewind.config import Config
from rewind.rollback.engine import (
    RollbackAction,
    plan_rollback,
    restore,
    safety_errors_from,
    undo_last,
)
from rewind.rollback.safety import (
    SafetyError,
    check_paths_within_cwd,
    check_uncommitted_changes,
)
from rewind.sessions import SessionManager
from rewind.store.db import open_event_store
from rewind.store.models import Event, EventKind, FileSnapshot, Session


def _seed_simple_session(
    *,
    workspace: Path,
    config: Config,
    manager: SessionManager,
    pre_content: bytes,
    post_content: bytes,
) -> Path:
    target = workspace / "x.py"
    target.write_bytes(pre_content)
    store, blobs = manager.open_session("s1")
    blob_pre = blobs.write_bytes(pre_content)
    blob_post = blobs.write_bytes(post_content)
    store.upsert_session(Session(id="s1", started_at=0, cwd=str(workspace)))
    pre_id = store.insert_event(
        Event(session_id="s1", seq=1, ts=1, kind=EventKind.PRE_TOOL, tool_name="Edit")
    )
    store.insert_event(
        Event(session_id="s1", seq=2, ts=2, kind=EventKind.POST_TOOL, tool_name="Edit")
    )
    store.insert_file_snapshot(
        FileSnapshot(
            event_id=pre_id,
            path=str(target),
            before_hash=blob_pre,
            after_hash=blob_post,
            bytes_before=len(pre_content),
            bytes_after=len(post_content),
        )
    )
    store.close()
    target.write_bytes(post_content)
    return target


def test_plan_rollback_restores_changed_file(
    workspace: Path, config: Config, manager: SessionManager
) -> None:
    target = _seed_simple_session(
        workspace=workspace,
        config=config,
        manager=manager,
        pre_content=b"hello\n",
        post_content=b"hello, world\n",
    )
    paths = manager.session_paths("s1")
    with open_event_store(paths.db) as store:
        plan = plan_rollback(store=store, session_id="s1", target_seq=2, cwd=workspace)
    assert len(plan.changes) == 1
    change = plan.changes[0]
    assert change.path == target
    assert change.action is RollbackAction.RESTORE


def test_plan_rollback_marks_unchanged_when_already_target(
    workspace: Path, config: Config, manager: SessionManager
) -> None:
    target = _seed_simple_session(
        workspace=workspace,
        config=config,
        manager=manager,
        pre_content=b"hello\n",
        post_content=b"hello, world\n",
    )
    target.write_bytes(b"hello\n")
    paths = manager.session_paths("s1")
    with open_event_store(paths.db) as store:
        plan = plan_rollback(store=store, session_id="s1", target_seq=2, cwd=workspace)
    assert plan.changes[0].action is RollbackAction.UNCHANGED


def test_plan_rollback_deletes_file_that_was_created(
    workspace: Path, config: Config, manager: SessionManager
) -> None:
    target = workspace / "new.py"
    target.write_bytes(b"new content\n")
    store, blobs = manager.open_session("s1")
    blob_post = blobs.write_bytes(b"new content\n")
    store.upsert_session(Session(id="s1", started_at=0, cwd=str(workspace)))
    pre_id = store.insert_event(
        Event(session_id="s1", seq=1, ts=1, kind=EventKind.PRE_TOOL, tool_name="Write")
    )
    store.insert_file_snapshot(
        FileSnapshot(
            event_id=pre_id,
            path=str(target),
            before_hash=None,
            after_hash=blob_post,
            bytes_before=None,
            bytes_after=len(b"new content\n"),
        )
    )
    store.close()
    paths = manager.session_paths("s1")
    with open_event_store(paths.db) as store:
        plan = plan_rollback(store=store, session_id="s1", target_seq=2, cwd=workspace)
    assert plan.changes[0].action is RollbackAction.DELETE


def test_plan_rollback_invalid_seq() -> None:
    config_dummy: Any = None  # not used
    _ = config_dummy
    with pytest.raises(ValueError):
        plan_rollback(
            store=None,  # type: ignore[arg-type]
            session_id="s1",
            target_seq=0,
            cwd=Path("/tmp"),
        )


def test_restore_writes_files_and_creates_checkpoint(
    workspace: Path, config: Config, manager: SessionManager
) -> None:
    target = _seed_simple_session(
        workspace=workspace,
        config=config,
        manager=manager,
        pre_content=b"hello\n",
        post_content=b"hello, world\n",
    )
    paths = manager.session_paths("s1")
    with open_event_store(paths.db) as store:
        plan = plan_rollback(store=store, session_id="s1", target_seq=2, cwd=workspace)
    outcome = restore(plan=plan, config=config, cwd=workspace, force=False)
    assert target.read_bytes() == b"hello\n"
    cp_dir = config.home / "checkpoints"
    assert any(cp_dir.glob("*.json"))
    assert outcome.plan.restored == 1


def test_undo_last_reverses(workspace: Path, config: Config, manager: SessionManager) -> None:
    target = _seed_simple_session(
        workspace=workspace,
        config=config,
        manager=manager,
        pre_content=b"v1\n",
        post_content=b"v2\n",
    )
    paths = manager.session_paths("s1")
    with open_event_store(paths.db) as store:
        plan = plan_rollback(store=store, session_id="s1", target_seq=2, cwd=workspace)
    restore(plan=plan, config=config, cwd=workspace, force=False)
    assert target.read_bytes() == b"v1\n"
    out = undo_last(config=config)
    assert out is not None
    assert target.read_bytes() == b"v2\n"


def test_undo_last_returns_none_without_checkpoints(config: Config) -> None:
    assert undo_last(config=config) is None


def test_check_paths_within_cwd_raises_on_escape(tmp_path: Path) -> None:
    cwd = tmp_path / "project"
    cwd.mkdir()
    outside = tmp_path / "elsewhere" / "x"
    outside.parent.mkdir()
    outside.write_text("x")
    with pytest.raises(SafetyError):
        check_paths_within_cwd([outside], cwd)


def test_check_paths_within_cwd_passes(tmp_path: Path) -> None:
    cwd = tmp_path / "p"
    cwd.mkdir()
    inside = cwd / "x"
    inside.write_text("x")
    check_paths_within_cwd([inside], cwd)


def test_check_uncommitted_changes_noop_for_non_git(tmp_path: Path) -> None:
    check_uncommitted_changes(tmp_path)


def test_safety_errors_from_paths_outside_cwd(
    workspace: Path, config: Config, manager: SessionManager, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("x")
    store, blobs = manager.open_session("s1")
    blob = blobs.write_bytes(b"x")
    store.upsert_session(Session(id="s1", started_at=0, cwd=str(workspace)))
    ev_id = store.insert_event(
        Event(session_id="s1", seq=1, ts=1, kind=EventKind.PRE_TOOL, tool_name="Write")
    )
    store.insert_file_snapshot(
        FileSnapshot(
            event_id=ev_id,
            path=str(outside),
            before_hash=blob,
            after_hash=blob,
            bytes_before=1,
            bytes_after=1,
        )
    )
    store.close()
    paths = manager.session_paths("s1")
    with open_event_store(paths.db) as store:
        plan = plan_rollback(store=store, session_id="s1", target_seq=2, cwd=workspace)
    # Outside paths are filtered at planning time, so the resulting plan
    # has no outside paths and the helper never raises.
    assert all(c.path != outside for c in plan.changes)
    list(safety_errors_from(plan, workspace))


def test_check_uncommitted_changes_with_clean_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    try:
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True, timeout=10)
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "x@x"],
            check=True,
            timeout=10,
        )
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "x"], check=True, timeout=10)
    except FileNotFoundError:
        pytest.skip("git not installed")
    check_uncommitted_changes(repo)
    (repo / "f").write_text("x")
    with pytest.raises(SafetyError):
        check_uncommitted_changes(repo)
