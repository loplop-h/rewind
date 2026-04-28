"""Session manager: high-level orchestration over :class:`EventStore` and :class:`BlobStore`.

A :class:`SessionManager` knows how to:

- locate the active session id (from a stable marker file)
- open per-session storage on demand
- ingest hook payloads into events + file snapshots
- list, read, and delete sessions
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from rewind.config import Config
from rewind.store.blob import BlobStore
from rewind.store.db import EventStore, open_event_store
from rewind.store.models import Session, SessionSummary

CURRENT_SESSION_FILENAME = "current_session.txt"


@dataclass(frozen=True, slots=True)
class SessionPaths:
    """Filesystem paths owned by a single session."""

    root: Path
    db: Path
    blobs: Path

    @classmethod
    def from_config(cls, config: Config, session_id: str) -> SessionPaths:
        root = config.session_dir(session_id)
        return cls(root=root, db=root / "events.db", blobs=root)


class SessionManager:
    """Façade over the per-session storage layout.

    Methods that mutate the filesystem (``open_session``, ``delete_session``)
    create or delete the session's directory tree atomically where possible.
    """

    def __init__(self, config: Config) -> None:
        self._config = config

    @property
    def config(self) -> Config:
        return self._config

    def session_paths(self, session_id: str) -> SessionPaths:
        return SessionPaths.from_config(self._config, session_id)

    def has_session(self, session_id: str) -> bool:
        paths = self.session_paths(session_id)
        return paths.db.exists()

    def open_session(self, session_id: str) -> tuple[EventStore, BlobStore]:
        """Open the per-session SQLite store and blob store, creating dirs."""

        self._config.ensure_dirs()
        paths = self.session_paths(session_id)
        paths.root.mkdir(parents=True, exist_ok=True)
        store = open_event_store(paths.db)
        blobs = BlobStore(paths.blobs)
        blobs.ensure_dirs()
        return store, blobs

    def list_sessions(self) -> list[Session]:
        if not self._config.sessions_dir.exists():
            return []
        sessions: list[Session] = []
        for entry in sorted(self._config.sessions_dir.iterdir()):
            db = entry / "events.db"
            if not db.exists():
                continue
            with open_event_store(db) as store:
                sessions.extend(store.list_sessions())
        sessions.sort(key=lambda s: s.started_at, reverse=True)
        return sessions

    def list_summaries(self) -> Iterable[SessionSummary]:
        for session in self.list_sessions():
            paths = self.session_paths(session.id)
            with open_event_store(paths.db) as store:
                summary = store.session_summary(session.id)
                if summary is not None:
                    yield summary

    def delete_session(self, session_id: str) -> bool:
        paths = self.session_paths(session_id)
        if not paths.root.exists():
            return False
        for child in sorted(paths.root.rglob("*"), reverse=True):
            if child.is_file() or child.is_symlink():
                child.unlink(missing_ok=True)
            else:
                child.rmdir()
        paths.root.rmdir()
        return True

    def set_current_session(self, session_id: str) -> None:
        self._config.ensure_dirs()
        self._config.current_session_file.write_text(session_id, encoding="utf-8")

    def get_current_session(self) -> str | None:
        path = self._config.current_session_file
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8").strip()
        return text or None

    def clear_current_session(self) -> None:
        path = self._config.current_session_file
        path.unlink(missing_ok=True)

    def latest_session(self) -> Session | None:
        sessions = self.list_sessions()
        return sessions[0] if sessions else None
