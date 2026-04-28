"""Tests for tool classification + path extraction in :mod:`rewind.capture.snapshot`."""

from __future__ import annotations

from pathlib import Path

from rewind.capture.snapshot import (
    classify_tool_call,
    extract_paths_from_tool_input,
)
from rewind.store.models import ToolStatus


def test_classify_explicit_error_is_wasted() -> None:
    assert classify_tool_call("Bash", {"is_error": True}) is ToolStatus.WASTED
    assert classify_tool_call("Edit", {"error": "boom"}) is ToolStatus.WASTED
    assert classify_tool_call("Bash", {"success": False}) is ToolStatus.WASTED


def test_classify_nonzero_exit_is_wasted() -> None:
    assert classify_tool_call("Bash", {"exit_code": 1}) is ToolStatus.WASTED


def test_classify_known_productive_tool() -> None:
    assert classify_tool_call("Edit", {"success": True}) is ToolStatus.PRODUCTIVE
    assert classify_tool_call("MultiEdit", None) is ToolStatus.PRODUCTIVE


def test_classify_known_neutral_tool() -> None:
    assert classify_tool_call("Read", None) is ToolStatus.NEUTRAL
    assert classify_tool_call("Grep", {}) is ToolStatus.NEUTRAL


def test_classify_unknown_tool_defaults_neutral() -> None:
    assert classify_tool_call("MysteryTool", None) is ToolStatus.NEUTRAL


def test_extract_paths_from_write_input() -> None:
    paths = extract_paths_from_tool_input("Edit", {"file_path": "/tmp/x.py"})
    assert paths == [Path("/tmp/x.py")]


def test_extract_paths_for_notebook() -> None:
    paths = extract_paths_from_tool_input("NotebookEdit", {"notebook_path": "/tmp/n.ipynb"})
    assert paths == [Path("/tmp/n.ipynb")]


def test_extract_paths_empty_for_neutral_tool() -> None:
    assert extract_paths_from_tool_input("Read", {"file_path": "/x"}) == []


def test_extract_paths_empty_when_no_path_field() -> None:
    assert extract_paths_from_tool_input("Edit", {"command": "echo"}) == []
