"""Runtime configuration for rewind.

A single :class:`Config` dataclass loaded from ``~/.rewind/config.toml`` (when
present), with sensible defaults applied for everything else. The module also
exposes the canonical filesystem layout under :func:`Config.rewind_home`.
"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path

DEFAULT_RETENTION_SESSIONS = 30
DEFAULT_MAX_BLOB_BYTES = 10 * 1024 * 1024
DEFAULT_TOOL_OUTPUT_TRUNCATE_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class Config:
    """Resolved runtime configuration for rewind.

    All paths are absolute. The constructor enforces no validation by itself
    so it stays cheap; use :meth:`from_env` or :meth:`load` to get a fully
    populated instance.
    """

    home: Path
    retention_sessions: int = DEFAULT_RETENTION_SESSIONS
    max_blob_bytes: int = DEFAULT_MAX_BLOB_BYTES
    tool_output_truncate_bytes: int = DEFAULT_TOOL_OUTPUT_TRUNCATE_BYTES
    capture_disabled: bool = False
    extra: dict[str, object] = field(default_factory=dict)

    @property
    def sessions_dir(self) -> Path:
        return self.home / "sessions"

    @property
    def config_file(self) -> Path:
        return self.home / "config.toml"

    @property
    def current_session_file(self) -> Path:
        return self.home / "current_session.txt"

    def session_dir(self, session_id: str) -> Path:
        if not session_id or "/" in session_id or "\\" in session_id:
            raise ValueError(f"invalid session id: {session_id!r}")
        return self.sessions_dir / session_id

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Config:
        """Resolve the rewind home from REWIND_HOME or the user home dir."""

        env = env if env is not None else dict(os.environ)
        override = env.get("REWIND_HOME")
        home = Path(override).expanduser().resolve() if override else _default_home()
        return cls(home=home)

    @classmethod
    def load(cls, env: dict[str, str] | None = None) -> Config:
        """Load configuration: defaults, then ``config.toml`` overrides if present.

        Unknown keys are preserved in :attr:`extra` so future fields don't
        silently disappear when an older binary reads a newer config file.
        """

        base = cls.from_env(env=env)
        cfg_path = base.config_file
        if not cfg_path.exists():
            return base
        try:
            with cfg_path.open("rb") as fh:
                data = tomllib.load(fh)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            print(f"rewind: ignoring malformed config at {cfg_path}: {exc}", file=sys.stderr)
            return base
        return _merge(base, data)

    def ensure_dirs(self) -> None:
        """Create the rewind home and sessions dir if they do not exist."""

        self.home.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)


def _default_home() -> Path:
    return Path.home().resolve() / ".rewind"


_KNOWN_KEYS = {
    "retention_sessions",
    "max_blob_bytes",
    "tool_output_truncate_bytes",
    "capture_disabled",
}


def _merge(base: Config, data: dict[str, object]) -> Config:
    extras: dict[str, object] = dict(base.extra)
    retention = base.retention_sessions
    max_blob = base.max_blob_bytes
    truncate = base.tool_output_truncate_bytes
    capture_disabled = base.capture_disabled
    for key, value in data.items():
        if key == "retention_sessions" and isinstance(value, int):
            retention = value
        elif key == "max_blob_bytes" and isinstance(value, int):
            max_blob = value
        elif key == "tool_output_truncate_bytes" and isinstance(value, int):
            truncate = value
        elif key == "capture_disabled" and isinstance(value, bool):
            capture_disabled = value
        else:
            extras[key] = value
    return replace(
        base,
        retention_sessions=retention,
        max_blob_bytes=max_blob,
        tool_output_truncate_bytes=truncate,
        capture_disabled=capture_disabled,
        extra=extras,
    )
