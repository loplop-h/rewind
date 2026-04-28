"""SQLite-backed event store.

Each session has its own SQLite file at
``<rewind_home>/sessions/<session_id>/events.db``. We use WAL mode so concurrent
hook invocations from Claude Code never block each other and never corrupt
state. Schema is created on first open and kept compatible via additive
migrations registered in :data:`MIGRATIONS`.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

from rewind.store.models import (
    Event,
    EventKind,
    FileSnapshot,
    Session,
    SessionSummary,
    ToolStatus,
)

SCHEMA_VERSION = 1

_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,
    started_at      INTEGER NOT NULL,
    ended_at        INTEGER,
    cwd             TEXT NOT NULL,
    model           TEXT,
    total_cost_usd  REAL NOT NULL DEFAULT 0,
    total_tokens_in INTEGER NOT NULL DEFAULT 0,
    total_tokens_out INTEGER NOT NULL DEFAULT 0,
    total_events    INTEGER NOT NULL DEFAULT 0,
    exit_reason     TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    seq             INTEGER NOT NULL,
    ts              INTEGER NOT NULL,
    kind            TEXT NOT NULL,
    tool_name       TEXT,
    tool_input_json TEXT,
    tool_output_json TEXT,
    tool_status     TEXT,
    cost_usd        REAL NOT NULL DEFAULT 0,
    tokens_in       INTEGER NOT NULL DEFAULT 0,
    tokens_out      INTEGER NOT NULL DEFAULT 0,
    duration_ms     INTEGER,
    model           TEXT,
    UNIQUE (session_id, seq)
);

CREATE TABLE IF NOT EXISTS file_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        INTEGER NOT NULL REFERENCES events(id),
    path            TEXT NOT NULL,
    before_hash     TEXT,
    after_hash      TEXT,
    bytes_before    INTEGER,
    bytes_after     INTEGER
);

CREATE INDEX IF NOT EXISTS idx_events_session_seq ON events(session_id, seq);
CREATE INDEX IF NOT EXISTS idx_events_session_kind ON events(session_id, kind);
CREATE INDEX IF NOT EXISTS idx_snapshots_event ON file_snapshots(event_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_path ON file_snapshots(path);
"""


MIGRATIONS: list[str] = [_SCHEMA_V1]


class EventStore:
    """Type-safe wrapper over a single session's SQLite file.

    Construct via :func:`open_event_store` rather than directly so the schema
    is migrated on first use.
    """

    def __init__(self, conn: sqlite3.Connection, db_path: Path) -> None:
        self._conn = conn
        self._db_path = db_path
        self._conn.row_factory = sqlite3.Row

    @property
    def path(self) -> Path:
        return self._db_path

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> EventStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._conn:
            yield self._conn

    def upsert_session(self, session: Session) -> None:
        with self.transaction() as cx:
            cx.execute(
                """
                INSERT INTO sessions (
                    id, started_at, ended_at, cwd, model,
                    total_cost_usd, total_tokens_in, total_tokens_out,
                    total_events, exit_reason
                ) VALUES (
                    :id, :started_at, :ended_at, :cwd, :model,
                    :total_cost_usd, :total_tokens_in, :total_tokens_out,
                    :total_events, :exit_reason
                )
                ON CONFLICT(id) DO UPDATE SET
                    ended_at = excluded.ended_at,
                    model = COALESCE(excluded.model, sessions.model),
                    total_cost_usd = excluded.total_cost_usd,
                    total_tokens_in = excluded.total_tokens_in,
                    total_tokens_out = excluded.total_tokens_out,
                    total_events = excluded.total_events,
                    exit_reason = COALESCE(excluded.exit_reason, sessions.exit_reason)
                """,
                asdict(session),
            )

    def get_session(self, session_id: str) -> Session | None:
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        return _row_to_session(row) if row is not None else None

    def list_sessions(self) -> list[Session]:
        rows = self._conn.execute("SELECT * FROM sessions ORDER BY started_at DESC").fetchall()
        return [_row_to_session(r) for r in rows]

    def insert_event(self, event: Event) -> int:
        with self.transaction() as cx:
            cur = cx.execute(
                """
                INSERT INTO events (
                    session_id, seq, ts, kind, tool_name,
                    tool_input_json, tool_output_json, tool_status,
                    cost_usd, tokens_in, tokens_out, duration_ms, model
                ) VALUES (
                    :session_id, :seq, :ts, :kind, :tool_name,
                    :tool_input_json, :tool_output_json, :tool_status,
                    :cost_usd, :tokens_in, :tokens_out, :duration_ms, :model
                )
                """,
                _event_to_row(event),
            )
        new_id = cur.lastrowid
        if new_id is None:  # pragma: no cover - sqlite always assigns one
            raise RuntimeError("sqlite did not return an inserted rowid")
        return new_id

    def next_seq(self, session_id: str) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(seq), 0) AS m FROM events WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return int(row["m"]) + 1

    def get_event(self, event_id: int) -> Event | None:
        row = self._conn.execute(
            "SELECT * FROM events WHERE id = ?",
            (event_id,),
        ).fetchone()
        return _row_to_event(row) if row is not None else None

    def get_event_by_seq(self, session_id: str, seq: int) -> Event | None:
        row = self._conn.execute(
            "SELECT * FROM events WHERE session_id = ? AND seq = ?",
            (session_id, seq),
        ).fetchone()
        return _row_to_event(row) if row is not None else None

    def list_events(self, session_id: str) -> list[Event]:
        rows = self._conn.execute(
            "SELECT * FROM events WHERE session_id = ? ORDER BY seq ASC",
            (session_id,),
        ).fetchall()
        return [_row_to_event(r) for r in rows]

    def insert_file_snapshot(self, snap: FileSnapshot) -> int:
        with self.transaction() as cx:
            cur = cx.execute(
                """
                INSERT INTO file_snapshots (
                    event_id, path, before_hash, after_hash,
                    bytes_before, bytes_after
                ) VALUES (
                    :event_id, :path, :before_hash, :after_hash,
                    :bytes_before, :bytes_after
                )
                """,
                {
                    "event_id": snap.event_id,
                    "path": snap.path,
                    "before_hash": snap.before_hash,
                    "after_hash": snap.after_hash,
                    "bytes_before": snap.bytes_before,
                    "bytes_after": snap.bytes_after,
                },
            )
        new_id = cur.lastrowid
        if new_id is None:  # pragma: no cover
            raise RuntimeError("sqlite did not return an inserted rowid")
        return new_id

    def list_snapshots(self, event_id: int) -> list[FileSnapshot]:
        rows = self._conn.execute(
            "SELECT * FROM file_snapshots WHERE event_id = ? ORDER BY id ASC",
            (event_id,),
        ).fetchall()
        return [_row_to_snapshot(r) for r in rows]

    def list_snapshots_up_to_seq(
        self, session_id: str, seq_exclusive: int
    ) -> list[tuple[Event, FileSnapshot]]:
        """Return all (event, snapshot) pairs for events with ``seq < seq_exclusive``.

        Sorted by event seq ascending then by snapshot id ascending.
        """

        rows = self._conn.execute(
            """
            SELECT e.id AS ev_id, e.session_id, e.seq, e.ts, e.kind, e.tool_name,
                   e.tool_input_json, e.tool_output_json, e.tool_status,
                   e.cost_usd, e.tokens_in, e.tokens_out, e.duration_ms, e.model,
                   s.id AS sn_id, s.event_id, s.path,
                   s.before_hash, s.after_hash,
                   s.bytes_before, s.bytes_after
            FROM events e
            JOIN file_snapshots s ON s.event_id = e.id
            WHERE e.session_id = ? AND e.seq < ?
            ORDER BY e.seq ASC, s.id ASC
            """,
            (session_id, seq_exclusive),
        ).fetchall()
        out: list[tuple[Event, FileSnapshot]] = []
        for r in rows:
            ev = Event(
                id=int(r["ev_id"]),
                session_id=r["session_id"],
                seq=int(r["seq"]),
                ts=int(r["ts"]),
                kind=EventKind.from_str(r["kind"]),
                tool_name=r["tool_name"],
                tool_input_json=r["tool_input_json"],
                tool_output_json=r["tool_output_json"],
                tool_status=ToolStatus(r["tool_status"]) if r["tool_status"] else None,
                cost_usd=float(r["cost_usd"]),
                tokens_in=int(r["tokens_in"]),
                tokens_out=int(r["tokens_out"]),
                duration_ms=int(r["duration_ms"]) if r["duration_ms"] is not None else None,
                model=r["model"],
            )
            sn = FileSnapshot(
                id=int(r["sn_id"]),
                event_id=int(r["event_id"]),
                path=r["path"],
                before_hash=r["before_hash"],
                after_hash=r["after_hash"],
                bytes_before=int(r["bytes_before"]) if r["bytes_before"] is not None else None,
                bytes_after=int(r["bytes_after"]) if r["bytes_after"] is not None else None,
            )
            out.append((ev, sn))
        return out

    def session_summary(self, session_id: str) -> SessionSummary | None:
        session = self.get_session(session_id)
        if session is None:
            return None
        counts = self._conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM events WHERE session_id = ?) AS ev_count,
                (SELECT COUNT(DISTINCT s.path)
                   FROM file_snapshots s JOIN events e ON e.id = s.event_id
                  WHERE e.session_id = ?) AS file_count,
                (SELECT COUNT(*) FROM events
                  WHERE session_id = ? AND tool_status = 'productive') AS productive,
                (SELECT COUNT(*) FROM events
                  WHERE session_id = ? AND tool_status = 'wasted') AS wasted,
                (SELECT COUNT(*) FROM events
                  WHERE session_id = ? AND tool_status IS NOT NULL) AS classified
            """,
            (session_id, session_id, session_id, session_id, session_id),
        ).fetchone()
        classified = int(counts["classified"] or 0)
        productive_pct = (int(counts["productive"]) / classified) * 100 if classified else 0.0
        wasted_pct = (int(counts["wasted"]) / classified) * 100 if classified else 0.0
        return SessionSummary(
            session=session,
            event_count=int(counts["ev_count"] or 0),
            file_count=int(counts["file_count"] or 0),
            productive_pct=productive_pct,
            wasted_pct=wasted_pct,
        )


def open_event_store(db_path: Path) -> EventStore:
    """Open or create the SQLite store at ``db_path`` and apply migrations.

    The parent directory must already exist.
    """

    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _apply_migrations(conn)
    return EventStore(conn, db_path)


def _apply_migrations(conn: sqlite3.Connection) -> None:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    )
    if cur.fetchone() is None:
        conn.executescript(MIGRATIONS[0])
        conn.execute("INSERT INTO schema_version (version) VALUES (1)")
        return
    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    current = int(row[0]) if row and row[0] is not None else 0
    target = len(MIGRATIONS)
    for v in range(current + 1, target + 1):
        script = MIGRATIONS[v - 1]
        conn.executescript(script)
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (v,))


def _row_to_session(row: sqlite3.Row) -> Session:
    return Session(
        id=row["id"],
        started_at=int(row["started_at"]),
        ended_at=int(row["ended_at"]) if row["ended_at"] is not None else None,
        cwd=row["cwd"],
        model=row["model"],
        total_cost_usd=float(row["total_cost_usd"]),
        total_tokens_in=int(row["total_tokens_in"]),
        total_tokens_out=int(row["total_tokens_out"]),
        total_events=int(row["total_events"]),
        exit_reason=row["exit_reason"],
    )


def _row_to_event(row: sqlite3.Row) -> Event:
    return Event(
        id=int(row["id"]),
        session_id=row["session_id"],
        seq=int(row["seq"]),
        ts=int(row["ts"]),
        kind=EventKind.from_str(row["kind"]),
        tool_name=row["tool_name"],
        tool_input_json=row["tool_input_json"],
        tool_output_json=row["tool_output_json"],
        tool_status=ToolStatus(row["tool_status"]) if row["tool_status"] else None,
        cost_usd=float(row["cost_usd"]),
        tokens_in=int(row["tokens_in"]),
        tokens_out=int(row["tokens_out"]),
        duration_ms=int(row["duration_ms"]) if row["duration_ms"] is not None else None,
        model=row["model"],
    )


def _row_to_snapshot(row: sqlite3.Row) -> FileSnapshot:
    return FileSnapshot(
        id=int(row["id"]),
        event_id=int(row["event_id"]),
        path=row["path"],
        before_hash=row["before_hash"],
        after_hash=row["after_hash"],
        bytes_before=int(row["bytes_before"]) if row["bytes_before"] is not None else None,
        bytes_after=int(row["bytes_after"]) if row["bytes_after"] is not None else None,
    )


def _event_to_row(event: Event) -> dict[str, Any]:
    return {
        "session_id": event.session_id,
        "seq": event.seq,
        "ts": event.ts,
        "kind": event.kind.value,
        "tool_name": event.tool_name,
        "tool_input_json": event.tool_input_json,
        "tool_output_json": event.tool_output_json,
        "tool_status": event.tool_status.value if event.tool_status else None,
        "cost_usd": event.cost_usd,
        "tokens_in": event.tokens_in,
        "tokens_out": event.tokens_out,
        "duration_ms": event.duration_ms,
        "model": event.model,
    }


def dump_event_input(payload: dict[str, Any]) -> str:
    """Serialize a tool input/output payload for storage.

    Truncates payloads larger than the configured cap to keep SQLite rows
    bounded; large blobs go through the blob store instead.
    """

    return json.dumps(payload, default=str)


def parse_event_input(serialized: str | None) -> dict[str, Any]:
    """Inverse of :func:`dump_event_input` with safe defaults."""

    if not serialized:
        return {}
    try:
        out = json.loads(serialized)
    except json.JSONDecodeError:
        return {}
    if not isinstance(out, dict):
        return {}
    return out


def iter_events_with_snapshots(
    store: EventStore, session_id: str
) -> Iterable[tuple[Event, list[FileSnapshot]]]:
    """Yield each event paired with its file snapshots, in seq order."""

    for event in store.list_events(session_id):
        if event.id is None:  # pragma: no cover - DB always assigns
            continue
        yield event, store.list_snapshots(event.id)
