"""Terminal app entry points.

For V1 the TUI is non-interactive: it prints the timeline (and optionally one
event's diff) to the terminal. The full Live/Layout interactive experience
lands in V0.2 — we keep the surface stable so :func:`run_tui` can be
upgraded without a CLI rev.
"""

from __future__ import annotations

import io
from collections.abc import Iterable
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from rewind.config import Config
from rewind.sessions import SessionManager
from rewind.store.blob import BlobStore
from rewind.store.db import EventStore, open_event_store
from rewind.store.models import Event, FileSnapshot
from rewind.tui.diff import build_unified_diff, safe_decode
from rewind.tui.timeline import build_timeline_table


def render_session(
    *,
    events: Iterable[Event],
    title: str | None = None,
) -> str:
    """Return a string rendering of a session's timeline (used by tests + CLI)."""

    buffer = io.StringIO()
    console = Console(file=buffer, width=120, force_terminal=False, record=False)
    console.print(build_timeline_table(events, title=title))
    return buffer.getvalue()


def render_event_detail(
    *,
    event: Event,
    snapshots: Iterable[FileSnapshot],
    blobs: BlobStore,
) -> str:
    """Render a single event with diffs for its snapshots."""

    buffer = io.StringIO()
    console = Console(file=buffer, width=120, force_terminal=False, record=False)
    header = (
        f"#{event.seq}  {event.kind.value}  {event.tool_name or ''}  "
        f"status={event.tool_status.value if event.tool_status else '-'}"
    )
    console.print(Panel.fit(header, title="event"))
    if event.tool_input_json:
        console.print(Panel.fit(event.tool_input_json, title="input", style="yellow"))
    if event.tool_output_json:
        console.print(Panel.fit(event.tool_output_json, title="output", style="cyan"))
    for snap in snapshots:
        before = _read_blob_text(blobs, snap.before_hash)
        after = _read_blob_text(blobs, snap.after_hash)
        diff = build_unified_diff(
            before_text=before,
            after_text=after,
            path=snap.path,
        )
        console.print(Panel(diff, title=f"diff: {snap.path}"))
    return buffer.getvalue()


def _read_blob_text(blobs: BlobStore, digest: str | None) -> str:
    if digest is None:
        return ""
    try:
        return safe_decode(blobs.read_bytes(digest))
    except FileNotFoundError:
        return ""


def run_tui(
    *,
    config: Config,
    session_id: str | None,
    seq: int | None = None,
) -> int:
    """Print a timeline (and optional event detail) for ``session_id`` to stdout."""

    manager = SessionManager(config)
    if session_id is None:
        latest = manager.latest_session()
        if latest is None:
            Console().print("[yellow]no sessions captured yet[/yellow]")
            return 1
        session_id = latest.id

    paths = manager.session_paths(session_id)
    if not paths.db.exists():
        Console().print(f"[red]session not found: {session_id}[/red]")
        return 2

    store: EventStore = open_event_store(paths.db)
    try:
        events = store.list_events(session_id)
        rendered = render_session(events=events, title=f"rewind  ·  session {session_id}")
        print(rendered)
        if seq is not None:
            event = store.get_event_by_seq(session_id, seq)
            if event is None or event.id is None:
                Console().print(f"[red]event #{seq} not found in session {session_id}[/red]")
                return 3
            blobs = BlobStore(_blobs_root_from_db(paths.db))
            blobs.ensure_dirs()
            snapshots = store.list_snapshots(event.id)
            print(render_event_detail(event=event, snapshots=snapshots, blobs=blobs))
        return 0
    finally:
        store.close()


def _blobs_root_from_db(db_path: Path) -> Path:
    return db_path.parent
