"""End-to-end smoke tests for the CLI."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from rewind.cli import main
from rewind.config import Config
from rewind.sessions import SessionManager
from rewind.store.models import Event, EventKind, FileSnapshot, Session


def _capture(runner: CliRunner, raw: str, *, kind: str) -> object:
    return runner.invoke(main, ["capture", kind], input=raw, catch_exceptions=False)


def _payload(kind: str, **extra: object) -> str:
    base: dict[str, object] = {
        "session_id": "session-int-1",
        "transcript_path": "/tmp/t.jsonl",
        "cwd": "/tmp",
        "permission_mode": "default",
        "hook_event_name": kind,
    }
    base.update(extra)
    return json.dumps(base)


def test_version_command(rewind_home: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "rewind" in result.output


def test_capture_session_lifecycle(rewind_home: Path) -> None:
    runner = CliRunner()
    raw = _payload("SessionStart", source="startup", model="opus")
    r = _capture(runner, raw, kind="session-start")
    assert r.exit_code == 0
    r = _capture(
        runner,
        _payload("UserPromptSubmit", prompt="hi"),
        kind="user-prompt",
    )
    assert r.exit_code == 0
    r = _capture(
        runner,
        _payload(
            "Stop",
            exit_reason="normal",
            total_cost_usd=0.5,
            total_tokens_in=10,
            total_tokens_out=20,
            total_events=3,
        ),
        kind="session-end",
    )
    assert r.exit_code == 0
    list_r = runner.invoke(main, ["sessions", "list"])
    assert list_r.exit_code == 0
    assert "session-int-1" in list_r.output


def test_stats_command(rewind_home: Path) -> None:
    runner = CliRunner()
    _capture(runner, _payload("SessionStart"), kind="session-start")
    _capture(
        runner,
        _payload("UserPromptSubmit", prompt="x"),
        kind="user-prompt",
    )
    r = runner.invoke(main, ["stats", "--json"])
    assert r.exit_code == 0
    parsed = json.loads(r.output)
    assert parsed["session_id"] == "session-int-1"


def test_export_markdown_default(rewind_home: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    _capture(runner, _payload("SessionStart"), kind="session-start")
    _capture(
        runner,
        _payload("UserPromptSubmit", prompt="describe the project"),
        kind="user-prompt",
    )
    out_file = tmp_path / "session.md"
    r = runner.invoke(main, ["export", "--out", str(out_file)])
    assert r.exit_code == 0
    text = out_file.read_text(encoding="utf-8")
    assert "rewind" in text
    assert "describe the project" in text


def test_capture_no_input_is_quiet(rewind_home: Path) -> None:
    runner = CliRunner()
    r = runner.invoke(main, ["capture", "user-prompt"], input="")
    assert r.exit_code == 0


def test_capture_invalid_payload_logs_error(rewind_home: Path) -> None:
    runner = CliRunner()
    r = runner.invoke(main, ["capture", "user-prompt"], input="{not json")
    assert r.exit_code == 0
    assert "rewind:" in r.output or r.stderr_bytes


def test_sessions_list_empty(rewind_home: Path) -> None:
    runner = CliRunner()
    r = runner.invoke(main, ["sessions", "list"])
    assert r.exit_code == 0
    assert "no sessions" in r.output


def test_sessions_delete_force(rewind_home: Path) -> None:
    runner = CliRunner()
    _capture(runner, _payload("SessionStart"), kind="session-start")
    r = runner.invoke(main, ["sessions", "delete", "session-int-1", "--force"])
    assert r.exit_code == 0


def test_cc_status_not_installed(rewind_home: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    r = runner.invoke(main, ["cc", "status", "--scope", "project", "--project-dir", str(tmp_path)])
    assert r.exit_code == 0
    assert "not installed" in r.output


def test_cc_setup_and_uninstall(rewind_home: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    project = tmp_path / "proj"
    project.mkdir()
    r = runner.invoke(main, ["cc", "setup", "--scope", "project", "--project-dir", str(project)])
    assert r.exit_code == 0
    settings = project / ".claude" / "settings.json"
    assert settings.exists()
    r = runner.invoke(main, ["cc", "status", "--scope", "project", "--project-dir", str(project)])
    assert r.exit_code == 0
    assert "installed" in r.output
    r = runner.invoke(
        main,
        ["cc", "uninstall", "--scope", "project", "--project-dir", str(project)],
    )
    assert r.exit_code == 0


def test_undo_when_nothing(rewind_home: Path) -> None:
    runner = CliRunner()
    r = runner.invoke(main, ["undo"])
    assert r.exit_code == 1


def test_goto_dry_run_with_seed(rewind_home: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    project = tmp_path / "proj"
    project.mkdir()
    target = project / "x.py"
    target.write_text("hello\n", encoding="utf-8")
    config = Config.from_env()
    config.ensure_dirs()
    manager = SessionManager(config)
    store, blobs = manager.open_session("seed-1")
    blob_pre = blobs.write_bytes(b"hello\n")
    blob_post = blobs.write_bytes(b"hello world\n")
    store.upsert_session(Session(id="seed-1", started_at=0, cwd=str(project)))
    pre_id = store.insert_event(
        Event(session_id="seed-1", seq=1, ts=1, kind=EventKind.PRE_TOOL, tool_name="Edit")
    )
    store.insert_event(
        Event(session_id="seed-1", seq=2, ts=2, kind=EventKind.POST_TOOL, tool_name="Edit")
    )
    store.insert_file_snapshot(
        FileSnapshot(
            event_id=pre_id,
            path=str(target),
            before_hash=blob_pre,
            after_hash=blob_post,
            bytes_before=len(b"hello\n"),
            bytes_after=len(b"hello world\n"),
        )
    )
    store.close()
    target.write_text("hello world\n", encoding="utf-8")
    r = runner.invoke(
        main,
        [
            "goto",
            "2",
            "--session",
            "seed-1",
            "--cwd",
            str(project),
            "--dry-run",
        ],
    )
    assert r.exit_code == 0
    # File should not have been modified.
    assert target.read_text(encoding="utf-8") == "hello world\n"


def test_module_entrypoint_runs(rewind_home: Path) -> None:
    if shutil.which(sys.executable) is None:  # pragma: no cover - sanity
        pytest.skip("python executable not on PATH")
    result = subprocess.run(
        [sys.executable, "-m", "rewind", "--version"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0
    assert "rewind" in result.stdout
