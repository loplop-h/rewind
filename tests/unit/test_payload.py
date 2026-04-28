"""Tests for the hook payload parser."""

from __future__ import annotations

import json
from typing import Any

import pytest

from rewind.capture.payload import (
    PostToolPayload,
    PreToolPayload,
    SessionEndPayload,
    SessionStartPayload,
    UserPromptPayload,
    parse_payload,
)
from rewind.store.models import EventKind


def _make(hook_name: str, **extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "session_id": "s1",
        "transcript_path": "/tmp/t.jsonl",
        "cwd": "/tmp",
        "permission_mode": "default",
        "hook_event_name": hook_name,
    }
    base.update(extra)
    return base


def test_parse_session_start_typed() -> None:
    raw = _make("SessionStart", source="startup", model="claude-opus-4-7")
    payload = parse_payload(raw)
    assert isinstance(payload, SessionStartPayload)
    assert payload.kind is EventKind.SESSION_START
    assert payload.source == "startup"
    assert payload.model == "claude-opus-4-7"


def test_parse_user_prompt_default_empty() -> None:
    raw = _make("UserPromptSubmit")
    payload = parse_payload(raw)
    assert isinstance(payload, UserPromptPayload)
    assert payload.prompt == ""


def test_parse_pre_tool_carries_input() -> None:
    raw = _make(
        "PreToolUse",
        tool_name="Edit",
        tool_input={"file_path": "/tmp/x.py", "old_string": "a", "new_string": "b"},
        tool_use_id="toolu_01",
    )
    payload = parse_payload(raw)
    assert isinstance(payload, PreToolPayload)
    assert payload.tool_input["file_path"] == "/tmp/x.py"
    assert payload.tool_use_id == "toolu_01"


def test_parse_post_tool_carries_response() -> None:
    raw = _make(
        "PostToolUse",
        tool_name="Bash",
        tool_input={"command": "echo ok"},
        tool_response={"stdout": "ok\n", "exit_code": 0},
        duration_ms=42,
    )
    payload = parse_payload(raw)
    assert isinstance(payload, PostToolPayload)
    assert payload.duration_ms == 42
    assert payload.tool_response["exit_code"] == 0


def test_parse_session_end_aggregates() -> None:
    raw = _make(
        "Stop",
        exit_reason="normal",
        total_cost_usd=1.23,
        total_tokens_in=10,
        total_tokens_out=20,
        total_events=5,
    )
    payload = parse_payload(raw)
    assert isinstance(payload, SessionEndPayload)
    assert payload.total_cost_usd == 1.23
    assert payload.total_events == 5


def test_parse_accepts_dict_or_string() -> None:
    raw_str = json.dumps(_make("UserPromptSubmit", prompt="hi"))
    raw_dict = _make("UserPromptSubmit", prompt="hi")
    assert parse_payload(raw_str).prompt == "hi"  # type: ignore[attr-defined]
    assert parse_payload(raw_dict).prompt == "hi"  # type: ignore[attr-defined]


def test_parse_rejects_non_object() -> None:
    with pytest.raises(ValueError):
        parse_payload("[1,2]")


def test_parse_rejects_invalid_json() -> None:
    with pytest.raises(ValueError):
        parse_payload("{not json")


def test_parse_rejects_missing_envelope() -> None:
    with pytest.raises(ValueError):
        parse_payload({"hook_event_name": "PreToolUse"})


def test_parse_rejects_unknown_event_name() -> None:
    raw = _make("MysteryEvent")
    with pytest.raises(ValueError):
        parse_payload(raw)


def test_parse_handles_non_dict_tool_input() -> None:
    raw = _make("PreToolUse", tool_name="X", tool_input="not-a-dict")
    payload = parse_payload(raw)
    assert isinstance(payload, PreToolPayload)
    assert payload.tool_input == {}
