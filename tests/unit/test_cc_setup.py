"""Tests for the Claude Code settings integration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rewind.cc_setup import (
    SETUP_HOOK_NAMES,
    install_claude_code_hooks,
    locate_claude_code_settings,
    show_status,
    uninstall_claude_code_hooks,
)
from rewind.config import Config


def _settings(tmp_path: Path) -> Path:
    p = tmp_path / "settings.json"
    p.write_text("{}", encoding="utf-8")
    return p


def test_locate_user_scope(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("rewind.cc_setup.Path.home", lambda: tmp_path)
    out = locate_claude_code_settings(scope="user")
    assert out == tmp_path / ".claude" / "settings.json"


def test_locate_project_scope(tmp_path: Path) -> None:
    out = locate_claude_code_settings(scope="project", project_dir=tmp_path)
    assert out == tmp_path / ".claude" / "settings.json"


def test_locate_unknown_scope_raises() -> None:
    with pytest.raises(ValueError):
        locate_claude_code_settings(scope="server")  # type: ignore[arg-type]


def test_install_creates_all_hooks(tmp_path: Path, config: Config) -> None:
    settings = _settings(tmp_path)
    install_claude_code_hooks(
        settings_path=settings,
        rewind_command="python -m rewind capture",
        config=config,
    )
    data = json.loads(settings.read_text(encoding="utf-8"))
    for name in SETUP_HOOK_NAMES:
        assert name in data["hooks"]
        bucket = data["hooks"][name]
        assert isinstance(bucket, list)
        commands = [h.get("command") for entry in bucket for h in entry["hooks"]]
        assert any("rewind capture" in str(cmd) for cmd in commands)


def test_install_is_idempotent(tmp_path: Path, config: Config) -> None:
    settings = _settings(tmp_path)
    install_claude_code_hooks(
        settings_path=settings,
        rewind_command="python -m rewind capture",
        config=config,
    )
    install_claude_code_hooks(
        settings_path=settings,
        rewind_command="python -m rewind capture",
        config=config,
    )
    data = json.loads(settings.read_text(encoding="utf-8"))
    for name in SETUP_HOOK_NAMES:
        assert len(data["hooks"][name]) == 1


def test_install_keeps_other_settings(tmp_path: Path, config: Config) -> None:
    settings = tmp_path / "s.json"
    settings.write_text(json.dumps({"editor": "code", "theme": "dark"}), encoding="utf-8")
    install_claude_code_hooks(
        settings_path=settings,
        rewind_command="python -m rewind capture",
        config=config,
    )
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["editor"] == "code"
    assert data["theme"] == "dark"


def test_install_writes_backup(tmp_path: Path, config: Config) -> None:
    settings = tmp_path / "s.json"
    settings.write_text(json.dumps({"x": 1}), encoding="utf-8")
    install_claude_code_hooks(
        settings_path=settings,
        rewind_command="python -m rewind capture",
        config=config,
    )
    backup = settings.with_suffix(settings.suffix + ".rewind-backup")
    assert backup.exists()
    assert json.loads(backup.read_text(encoding="utf-8")) == {"x": 1}


def test_uninstall_removes_only_rewind_entries(tmp_path: Path, config: Config) -> None:
    settings = _settings(tmp_path)
    install_claude_code_hooks(
        settings_path=settings,
        rewind_command="python -m rewind capture",
        config=config,
    )
    data = json.loads(settings.read_text(encoding="utf-8"))
    data["hooks"]["PreToolUse"].append(
        {"matcher": "Bash", "hooks": [{"type": "command", "command": "/x.sh"}]}
    )
    settings.write_text(json.dumps(data), encoding="utf-8")
    assert uninstall_claude_code_hooks(settings_path=settings) is True
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["hooks"]["PreToolUse"][0]["matcher"] == "Bash"
    assert "SessionStart" not in data["hooks"]


def test_uninstall_returns_false_for_missing_file(tmp_path: Path) -> None:
    assert uninstall_claude_code_hooks(settings_path=tmp_path / "nope.json") is False


def test_show_status_variants(tmp_path: Path, config: Config) -> None:
    missing = tmp_path / "missing.json"
    assert "not installed" in show_status(missing)
    settings = _settings(tmp_path)
    assert "not installed" in show_status(settings)
    install_claude_code_hooks(
        settings_path=settings,
        rewind_command="python -m rewind capture",
        config=config,
    )
    msg = show_status(settings)
    assert "installed" in msg
    settings.write_text("{not json}", encoding="utf-8")
    assert "invalid" in show_status(settings)


def test_install_rejects_corrupt_settings(tmp_path: Path, config: Config) -> None:
    settings = tmp_path / "s.json"
    settings.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        install_claude_code_hooks(
            settings_path=settings,
            rewind_command="python -m rewind capture",
            config=config,
        )


def test_install_handles_empty_file(tmp_path: Path, config: Config) -> None:
    settings = tmp_path / "s.json"
    settings.write_text("", encoding="utf-8")
    install_claude_code_hooks(
        settings_path=settings,
        rewind_command="python -m rewind capture",
        config=config,
    )
    assert settings.exists()
