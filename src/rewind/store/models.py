"""Domain models for the rewind event store.

All models are frozen dataclasses with explicit slots. They are passed by
value across the storage boundary and never mutated in place. The schema in
:mod:`rewind.store.db` is the source of truth for column types; these
classes mirror it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class EventKind(StrEnum):
    """The five Claude Code lifecycle events we capture."""

    SESSION_START = "session_start"
    USER_PROMPT = "user_prompt"
    PRE_TOOL = "pre_tool"
    POST_TOOL = "post_tool"
    SESSION_END = "session_end"

    @classmethod
    def from_str(cls, value: str) -> EventKind:
        try:
            return cls(value)
        except ValueError as exc:
            valid = ", ".join(k.value for k in cls)
            raise ValueError(f"unknown event kind {value!r} (valid: {valid})") from exc


class ToolStatus(StrEnum):
    """Coarse classification of a tool call's outcome.

    Mirrors the ``spent`` taxonomy so the two products can interoperate.
    """

    PRODUCTIVE = "productive"
    NEUTRAL = "neutral"
    WASTED = "wasted"


@dataclass(frozen=True, slots=True, kw_only=True)
class Session:
    """One Claude Code session, identified by Claude's own session id."""

    id: str
    started_at: int
    ended_at: int | None = None
    cwd: str
    model: str | None = None
    total_cost_usd: float = 0.0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_events: int = 0
    exit_reason: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Event:
    """A single captured event within a session.

    ``id`` is the autoincrement primary key (None until persisted).
    ``seq`` is the 1-based ordinal within the session and is what we
    expose to users (e.g. ``rewind goto 31``).
    """

    id: int | None = None
    session_id: str
    seq: int
    ts: int
    kind: EventKind
    tool_name: str | None = None
    tool_input_json: str | None = None
    tool_output_json: str | None = None
    tool_status: ToolStatus | None = None
    cost_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int | None = None
    model: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class FileSnapshot:
    """A before/after pair of file content hashes attached to an event.

    Conventions:

    * ``before_hash is None``  →  the file did not exist immediately before
      the event's tool ran.
    * ``after_hash is None``   →  the file does not exist immediately after
      (either the tool deleted it or it never existed and the post-tool also
      saw it absent).
    * Both ``None`` is legal during the pre-tool/post-tool transition for
      paths that were neither read nor created (rare but possible).
    """

    id: int | None = None
    event_id: int
    path: str
    before_hash: str | None = None
    after_hash: str | None = None
    bytes_before: int | None = None
    bytes_after: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SessionSummary:
    """Lightweight projection used by ``rewind sessions list``."""

    session: Session
    event_count: int
    file_count: int
    productive_pct: float = 0.0
    wasted_pct: float = 0.0
    extra: dict[str, object] = field(default_factory=dict)
