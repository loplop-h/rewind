"""Regression for the bash-on-Windows path bug fixed in 0.1.3.

The hook command written into Claude Code's ``settings.json`` is later
executed by ``/usr/bin/bash`` even on Windows (Git Bash / MSYS). Bash
interprets ``\\`` as an escape character, so a backslash-bearing path
silently collapses. We need:

1. **No backslashes** in the emitted command.
2. **The path quoted** so that any future spaces (e.g. "Program Files")
   don't break tokenisation.
3. **The remainder of the command — module name and subcommand — left
   alone** so we don't inadvertently break ``rewind capture <kind>``.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from rewind.cc_setup import install_claude_code_hooks
from rewind.cli import _self_command
from rewind.config import Config


def test_self_command_has_no_backslashes() -> None:
    """The command we hand to bash must contain zero backslashes.

    Backslashes survive being written into JSON (settings.json escapes them
    as ``\\\\``) but bash, on the other side, eats them again.
    """

    cmd = _self_command()
    assert "\\" not in cmd, f"backslashes leaked into hook command: {cmd!r}"


def test_self_command_quotes_executable_path() -> None:
    """The executable must be quoted with single quotes (literal in bash)."""

    cmd = _self_command()
    assert cmd.startswith("'"), f"command does not start with a quote: {cmd!r}"
    # The first quote-bounded token is the executable; assert it ends before
    # the rest of the command so spaces inside it would not break parsing.
    first_close = cmd.find("'", 1)
    assert first_close != -1, f"unterminated quote in command: {cmd!r}"


def test_self_command_uses_posix_style_path(monkeypatch: Any) -> None:
    """When ``sys.executable`` has Windows backslashes, the emitted command
    must convert to forward-slash POSIX form."""

    monkeypatch.setattr(sys, "executable", r"C:\Users\test\Python\python.exe")
    cmd = _self_command()
    # The raw drive letter / forward slashes must appear; backslashes must not.
    assert "C:/Users/test/Python/python.exe" in cmd
    assert "\\" not in cmd


def test_self_command_keeps_module_invocation() -> None:
    """The command must end with the module + subcommand we want bash to run."""

    cmd = _self_command()
    assert cmd.endswith("-m rewind capture"), f"command tail wrong: {cmd!r}"


def test_self_command_round_trips_through_settings(tmp_path: Any) -> None:
    """End-to-end: install hooks, read settings.json, ensure the stored
    command is bash-safe (no raw backslashes in the command field)."""

    home = tmp_path / "rewind_home"
    settings = tmp_path / "settings.json"
    settings.write_text("{}", encoding="utf-8")

    install_claude_code_hooks(
        settings_path=settings,
        rewind_command=_self_command(),
        config=Config.from_env(env={"REWIND_HOME": str(home)}),
    )
    data = json.loads(settings.read_text(encoding="utf-8"))
    for bucket in data["hooks"].values():
        for entry in bucket:
            for hk in entry["hooks"]:
                command = hk["command"]
                assert "\\" not in command, f"backslash in stored hook command: {command!r}"
                assert "rewind capture" in command
