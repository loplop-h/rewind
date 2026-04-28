"""Shared pytest fixtures for the rewind test suite."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from rewind.config import Config
from rewind.sessions import SessionManager


@pytest.fixture()
def rewind_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated REWIND_HOME for the duration of a test."""

    home = tmp_path / "rewind_home"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("REWIND_HOME", str(home))
    return home


@pytest.fixture()
def config(rewind_home: Path) -> Config:
    cfg = Config.from_env()
    cfg.ensure_dirs()
    return cfg


@pytest.fixture()
def manager(config: Config) -> SessionManager:
    return SessionManager(config)


@pytest.fixture()
def sample_session_id() -> str:
    return "session-abcdef123456"


@pytest.fixture()
def make_payload() -> Any:
    """Factory: build the JSON envelope Claude Code sends to a hook."""

    def _factory(
        *,
        hook_event_name: str,
        session_id: str = "session-abcdef123456",
        cwd: str = "/tmp/project",
        **extra: Any,
    ) -> str:
        base: dict[str, Any] = {
            "session_id": session_id,
            "transcript_path": "/tmp/project/.claude/transcript.jsonl",
            "cwd": cwd,
            "permission_mode": "default",
            "hook_event_name": hook_event_name,
        }
        base.update(extra)
        return json.dumps(base)

    return _factory


@pytest.fixture()
def workspace(tmp_path: Path) -> Iterator[Path]:
    """A throwaway "project" directory that tests can write to."""

    ws = tmp_path / "workspace"
    ws.mkdir()
    yield ws
