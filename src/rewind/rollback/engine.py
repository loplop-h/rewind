"""Rollback engine.

Computes the file-system delta required to restore the working tree to the
state immediately before a chosen event, then applies it atomically. Each
rollback writes a *checkpoint* of the current state first so :func:`undo_last`
can reverse it.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from rewind.config import Config
from rewind.rollback.safety import (
    SafetyError,
    check_paths_within_cwd,
    check_uncommitted_changes,
)
from rewind.sessions import SessionManager
from rewind.store.blob import BlobStore, hash_path
from rewind.store.db import EventStore
from rewind.store.models import FileSnapshot

CHECKPOINTS_DIRNAME = "checkpoints"


class RollbackAction(StrEnum):
    """One of three things we'll do to a path during rollback."""

    RESTORE = "restore"
    DELETE = "delete"
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True, kw_only=True)
class PlannedFileChange:
    """One file's planned rollback action."""

    path: Path
    action: RollbackAction
    target_hash: str | None
    current_hash: str | None
    target_bytes: int | None
    current_bytes: int | None


@dataclass(frozen=True, slots=True, kw_only=True)
class RollbackPlan:
    """The full plan: every file affected, the action, and a summary."""

    session_id: str
    target_seq: int
    changes: list[PlannedFileChange] = field(default_factory=list)

    @property
    def restored(self) -> int:
        return sum(1 for c in self.changes if c.action is RollbackAction.RESTORE)

    @property
    def deleted(self) -> int:
        return sum(1 for c in self.changes if c.action is RollbackAction.DELETE)

    @property
    def unchanged(self) -> int:
        return sum(1 for c in self.changes if c.action is RollbackAction.UNCHANGED)

    @property
    def affected(self) -> int:
        return self.restored + self.deleted


@dataclass(frozen=True, slots=True, kw_only=True)
class RollbackOutcome:
    """Result of executing a rollback. Used by tests, CLI, and TUI."""

    plan: RollbackPlan
    checkpoint_id: str
    cwd: Path


def plan_rollback(
    *,
    store: EventStore,
    session_id: str,
    target_seq: int,
    cwd: Path,
) -> RollbackPlan:
    """Compute (without applying) the file-system delta required to rollback.

    The plan only references paths inside ``cwd`` (after resolving). Paths
    outside ``cwd`` are ignored at planning time so the safety check can
    still raise on them explicitly.
    """

    if target_seq < 1:
        raise ValueError("target_seq must be >= 1")
    pairs = store.list_snapshots_up_to_seq(session_id, target_seq)
    latest_per_path: dict[str, FileSnapshot] = {}
    for _ev, snap in pairs:
        latest_per_path[snap.path] = snap

    earliest_per_path: dict[str, FileSnapshot] = {}
    for _ev, snap in pairs:
        earliest_per_path.setdefault(snap.path, snap)
    changes: list[PlannedFileChange] = []
    cwd_resolved = cwd.resolve()
    for raw_path in latest_per_path:
        path = Path(raw_path)
        first_snap = earliest_per_path[raw_path]
        target_hash = first_snap.before_hash
        target_bytes = first_snap.bytes_before
        target_existed = target_hash is not None
        try:
            path.resolve().relative_to(cwd_resolved)
        except ValueError:
            continue
        current_hash, current_bytes = _current_state(path)
        action = _decide_action(
            target_hash=target_hash,
            target_existed=target_existed,
            current_hash=current_hash,
        )
        changes.append(
            PlannedFileChange(
                path=path,
                action=action,
                target_hash=target_hash,
                current_hash=current_hash,
                target_bytes=target_bytes,
                current_bytes=current_bytes,
            )
        )
    changes.sort(key=lambda c: str(c.path))
    return RollbackPlan(session_id=session_id, target_seq=target_seq, changes=changes)


def _current_state(path: Path) -> tuple[str | None, int | None]:
    if not path.exists() or not path.is_file():
        return None, None
    digest, size = hash_path(path)
    return digest, size


def _decide_action(
    *,
    target_hash: str | None,
    target_existed: bool,
    current_hash: str | None,
) -> RollbackAction:
    if not target_existed:
        if current_hash is None:
            return RollbackAction.UNCHANGED
        return RollbackAction.DELETE
    if current_hash == target_hash:
        return RollbackAction.UNCHANGED
    return RollbackAction.RESTORE


def restore(
    *,
    plan: RollbackPlan,
    config: Config,
    cwd: Path,
    force: bool = False,
) -> RollbackOutcome:
    """Execute ``plan`` against the file system. Save a checkpoint first."""

    paths_to_touch = [c.path for c in plan.changes if c.action is not RollbackAction.UNCHANGED]
    if not force:
        check_paths_within_cwd(paths_to_touch, cwd)
        check_uncommitted_changes(cwd)
    elif not force:  # pragma: no cover
        raise AssertionError("unreachable")

    manager = SessionManager(config)
    _store, blobs = manager.open_session(plan.session_id)
    _store.close()

    checkpoint_id = _save_checkpoint(
        config=config,
        session_id=plan.session_id,
        plan=plan,
        blobs=blobs,
    )

    for change in plan.changes:
        if change.action is RollbackAction.RESTORE:
            assert change.target_hash is not None
            content = blobs.read_bytes(change.target_hash)
            change.path.parent.mkdir(parents=True, exist_ok=True)
            change.path.write_bytes(content)
        elif change.action is RollbackAction.DELETE:
            change.path.unlink(missing_ok=True)

    return RollbackOutcome(plan=plan, checkpoint_id=checkpoint_id, cwd=cwd)


@dataclass(frozen=True, slots=True, kw_only=True)
class _Checkpoint:
    """Internal record of a single rollback's pre-state."""

    id: str
    session_id: str
    target_seq: int
    cwd: str
    files: list[dict[str, object]]


def _save_checkpoint(
    *,
    config: Config,
    session_id: str,
    plan: RollbackPlan,
    blobs: BlobStore,
) -> str:
    checkpoints_dir = config.home / CHECKPOINTS_DIRNAME
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    cp_id = f"{int(time.time() * 1000)}-{session_id[:8]}"
    files_record: list[dict[str, object]] = []
    for change in plan.changes:
        if change.action is RollbackAction.UNCHANGED:
            continue
        if change.path.exists() and change.path.is_file():
            current_bytes = change.path.read_bytes()
            digest = blobs.write_bytes(current_bytes)
            files_record.append(
                {
                    "path": str(change.path),
                    "before_hash": digest,
                    "bytes_before": len(current_bytes),
                }
            )
        else:
            files_record.append(
                {
                    "path": str(change.path),
                    "before_hash": None,
                    "bytes_before": None,
                }
            )
    record = {
        "id": cp_id,
        "session_id": session_id,
        "target_seq": plan.target_seq,
        "files": files_record,
        "saved_at": int(time.time() * 1000),
    }
    (checkpoints_dir / f"{cp_id}.json").write_text(json.dumps(record), encoding="utf-8")
    return cp_id


def undo_last(*, config: Config) -> RollbackOutcome | None:
    """Reverse the most recent rollback by replaying its checkpoint."""

    checkpoints_dir = config.home / CHECKPOINTS_DIRNAME
    if not checkpoints_dir.exists():
        return None
    candidates = sorted(checkpoints_dir.glob("*.json"))
    if not candidates:
        return None
    last = candidates[-1]
    record = json.loads(last.read_text(encoding="utf-8"))
    session_id = str(record["session_id"])
    manager = SessionManager(config)
    _store, blobs = manager.open_session(session_id)
    _store.close()
    changes: list[PlannedFileChange] = []
    for entry in record.get("files", []):
        path = Path(str(entry["path"]))
        before_hash = entry.get("before_hash")
        bytes_before = entry.get("bytes_before")
        if before_hash is None:
            action = RollbackAction.DELETE
        else:
            action = RollbackAction.RESTORE
            content = blobs.read_bytes(str(before_hash))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        changes.append(
            PlannedFileChange(
                path=path,
                action=action,
                target_hash=before_hash if isinstance(before_hash, str) else None,
                current_hash=None,
                target_bytes=int(bytes_before) if isinstance(bytes_before, int) else None,
                current_bytes=None,
            )
        )
        if action is RollbackAction.DELETE:
            path.unlink(missing_ok=True)
    plan = RollbackPlan(
        session_id=session_id,
        target_seq=int(record.get("target_seq", 0)),
        changes=changes,
    )
    last.unlink(missing_ok=True)
    return RollbackOutcome(plan=plan, checkpoint_id=str(record["id"]), cwd=Path.cwd())


def safety_errors_from(plan: RollbackPlan, cwd: Path) -> Iterable[SafetyError]:
    """Yield SafetyErrors that would be raised by :func:`restore` (without raising)."""

    paths = [c.path for c in plan.changes if c.action is not RollbackAction.UNCHANGED]
    try:
        check_paths_within_cwd(paths, cwd)
    except SafetyError as exc:
        yield exc
    try:
        check_uncommitted_changes(cwd)
    except SafetyError as exc:
        yield exc
