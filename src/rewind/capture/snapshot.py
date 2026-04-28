"""File snapshot capture for Edit/Write/MultiEdit/NotebookEdit tool calls.

We record a content-addressed blob of every file touched by a write-style
tool, both before the tool ran (for rollback) and after (so the timeline
shows the diff). For non-write tools we record nothing — this keeps the
storage cost proportional to actual destructive behaviour.

The classifier (:func:`classify_tool_call`) mirrors the ``spent`` taxonomy
of productive / neutral / wasted so the two products' analytics align.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from rewind.store.blob import BlobStore, hash_path
from rewind.store.db import EventStore
from rewind.store.models import FileSnapshot, ToolStatus

WRITE_TOOLS: frozenset[str] = frozenset(
    {
        "Write",
        "Edit",
        "MultiEdit",
        "NotebookEdit",
    }
)

PRODUCTIVE_TOOLS: frozenset[str] = frozenset(
    {
        "Write",
        "Edit",
        "MultiEdit",
        "NotebookEdit",
        "TodoWrite",
        "TaskCreate",
        "TaskUpdate",
    }
)

NEUTRAL_TOOLS: frozenset[str] = frozenset(
    {
        "Read",
        "Grep",
        "Glob",
        "ListDir",
        "WebFetch",
        "WebSearch",
        "TaskList",
        "TaskGet",
    }
)

WASTED_HINT_KEYS: frozenset[str] = frozenset({"error", "exit_code"})


def classify_tool_call(
    tool_name: str | None,
    tool_response: dict[str, Any] | None,
) -> ToolStatus:
    """Heuristic classification of a tool call's outcome.

    Rules, in order:

    1. If we have a response with an explicit error indicator → ``WASTED``.
    2. If the tool is in :data:`PRODUCTIVE_TOOLS` → ``PRODUCTIVE``.
    3. If the tool is in :data:`NEUTRAL_TOOLS` → ``NEUTRAL``.
    4. Otherwise → ``NEUTRAL`` (safe default).
    """

    if tool_response is not None:
        if tool_response.get("is_error") is True or tool_response.get("error"):
            return ToolStatus.WASTED
        success = tool_response.get("success")
        if success is False:
            return ToolStatus.WASTED
        exit_code = tool_response.get("exit_code")
        if isinstance(exit_code, int) and exit_code != 0:
            return ToolStatus.WASTED
    if tool_name in PRODUCTIVE_TOOLS:
        return ToolStatus.PRODUCTIVE
    if tool_name in NEUTRAL_TOOLS:
        return ToolStatus.NEUTRAL
    return ToolStatus.NEUTRAL


def extract_paths_from_tool_input(
    tool_name: str,
    tool_input: dict[str, Any],
) -> list[Path]:
    """Pull every absolute path the tool will read or write from its input.

    The Claude Code tool schemas use a ``file_path`` (and sometimes
    ``notebook_path``) field; ``MultiEdit`` puts a single path at the top
    level even when applying multiple edits. Returns an empty list for
    tools we don't recognise.
    """

    if tool_name not in WRITE_TOOLS:
        return []
    out: list[Path] = []
    for key in ("file_path", "notebook_path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            out.append(Path(value))
    return out


def record_pre_tool_snapshot(
    *,
    store: EventStore,
    blobs: BlobStore,
    event_id: int,
    tool_name: str,
    tool_input: dict[str, Any],
) -> list[FileSnapshot]:
    """Snapshot the *before* state of all files this tool will touch.

    For each path:

    * If the file exists, hash its bytes via :class:`BlobStore` and record
      ``before_hash`` and ``bytes_before``.
    * If the file does not exist, record a snapshot with ``before_hash=None``
      and ``after_hash=None`` is forbidden, so we use a sentinel marker
      using the empty-content blob (sha256 of zero bytes) and bytes_before=0
      so the model's invariant holds. The post-tool record will fix the
      after-hash.
    """

    snapshots: list[FileSnapshot] = []
    for path in extract_paths_from_tool_input(tool_name, tool_input):
        snap = _capture_pre(store=store, blobs=blobs, event_id=event_id, path=path)
        if snap is not None:
            snapshots.append(snap)
    return snapshots


def record_post_tool_snapshot(
    *,
    store: EventStore,
    blobs: BlobStore,
    pre_event_id: int | None,
    post_event_id: int,
    tool_name: str,
    tool_input: dict[str, Any],
) -> list[FileSnapshot]:
    """Snapshot the *after* state and link it to the pre-event when possible.

    If we have a matching pre-event id we update its row in place; otherwise
    we create a fresh after-only snapshot row attached to the post-event.
    """

    snapshots: list[FileSnapshot] = []
    for path in extract_paths_from_tool_input(tool_name, tool_input):
        snap = _capture_post(
            store=store,
            blobs=blobs,
            pre_event_id=pre_event_id,
            post_event_id=post_event_id,
            path=path,
        )
        if snap is not None:
            snapshots.append(snap)
    return snapshots


def _capture_pre(
    *,
    store: EventStore,
    blobs: BlobStore,
    event_id: int,
    path: Path,
) -> FileSnapshot | None:
    if path.exists() and path.is_file():
        digest, size = hash_path(path)
        blobs.write_bytes(path.read_bytes())
        snap = FileSnapshot(
            event_id=event_id,
            path=str(path),
            before_hash=digest,
            after_hash=None,
            bytes_before=size,
            bytes_after=None,
        )
    else:
        snap = FileSnapshot(
            event_id=event_id,
            path=str(path),
            before_hash=None,
            after_hash=None,
            bytes_before=None,
            bytes_after=None,
        )
    snap_id = store.insert_file_snapshot(snap)
    return FileSnapshot(
        id=snap_id,
        event_id=snap.event_id,
        path=snap.path,
        before_hash=snap.before_hash,
        after_hash=snap.after_hash,
        bytes_before=snap.bytes_before,
        bytes_after=snap.bytes_after,
    )


def _capture_post(
    *,
    store: EventStore,
    blobs: BlobStore,
    pre_event_id: int | None,
    post_event_id: int,
    path: Path,
) -> FileSnapshot | None:
    if path.exists() and path.is_file():
        digest, size = hash_path(path)
        blobs.write_bytes(path.read_bytes())
        after_hash: str | None = digest
        bytes_after: int | None = size
    else:
        after_hash = None
        bytes_after = None

    pre_snap = _find_pre_snapshot(store, pre_event_id, str(path)) if pre_event_id else None
    if pre_snap is not None and pre_snap.id is not None:
        with store.transaction() as cx:
            cx.execute(
                "UPDATE file_snapshots SET after_hash = ?, bytes_after = ? WHERE id = ?",
                (after_hash, bytes_after, pre_snap.id),
            )
        return FileSnapshot(
            id=pre_snap.id,
            event_id=pre_snap.event_id,
            path=pre_snap.path,
            before_hash=pre_snap.before_hash,
            after_hash=after_hash,
            bytes_before=pre_snap.bytes_before,
            bytes_after=bytes_after,
        )
    snap = FileSnapshot(
        event_id=post_event_id,
        path=str(path),
        before_hash=None,
        after_hash=after_hash,
        bytes_before=None,
        bytes_after=bytes_after,
    )
    snap_id = store.insert_file_snapshot(snap)
    return FileSnapshot(
        id=snap_id,
        event_id=snap.event_id,
        path=snap.path,
        before_hash=snap.before_hash,
        after_hash=snap.after_hash,
        bytes_before=snap.bytes_before,
        bytes_after=snap.bytes_after,
    )


def _find_pre_snapshot(
    store: EventStore,
    pre_event_id: int | None,
    path: str,
) -> FileSnapshot | None:
    if pre_event_id is None:
        return None
    for snap in store.list_snapshots(pre_event_id):
        if snap.path == path and snap.after_hash is None:
            return snap
    return None


def chain_paths(snapshots: Iterable[FileSnapshot]) -> dict[str, FileSnapshot]:
    """Reduce a sequence of snapshots to the *latest* one per path."""

    out: dict[str, FileSnapshot] = {}
    for snap in snapshots:
        out[snap.path] = snap
    return out
