"""Parsers for the JSON payloads Claude Code sends to hook commands via stdin.

Each :class:`HookPayload` subclass is the canonical, validated form of one
hook event. The :func:`parse_payload` entry point dispatches by
``hook_event_name`` and produces the right subclass.

The parsers are deliberately permissive: missing optional fields default to
sensible values rather than raising. We only raise for genuinely malformed
input (not a JSON object, missing the envelope ``hook_event_name``, etc.).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from rewind.store.models import EventKind


@dataclass(frozen=True, slots=True, kw_only=True)
class HookPayload:
    """Common envelope shared by all Claude Code hook events."""

    session_id: str
    transcript_path: str | None = None
    cwd: str
    permission_mode: str | None = None
    hook_event_name: str

    @property
    def kind(self) -> EventKind:
        return _hook_to_kind(self.hook_event_name)


@dataclass(frozen=True, slots=True, kw_only=True)
class SessionStartPayload(HookPayload):
    source: str | None = None
    model: str | None = None
    agent_type: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class UserPromptPayload(HookPayload):
    prompt: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class PreToolPayload(HookPayload):
    tool_name: str
    tool_input: dict[str, Any]
    tool_use_id: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class PostToolPayload(HookPayload):
    tool_name: str
    tool_input: dict[str, Any]
    tool_response: dict[str, Any]
    tool_use_id: str | None = None
    duration_ms: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SessionEndPayload(HookPayload):
    exit_reason: str | None = None
    total_cost_usd: float = 0.0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_events: int = 0


_HOOK_NAME_TO_KIND = {
    "SessionStart": EventKind.SESSION_START,
    "UserPromptSubmit": EventKind.USER_PROMPT,
    "PreToolUse": EventKind.PRE_TOOL,
    "PostToolUse": EventKind.POST_TOOL,
    "Stop": EventKind.SESSION_END,
}


def _hook_to_kind(hook_event_name: str) -> EventKind:
    try:
        return _HOOK_NAME_TO_KIND[hook_event_name]
    except KeyError as exc:
        valid = ", ".join(_HOOK_NAME_TO_KIND)
        raise ValueError(
            f"unsupported hook_event_name: {hook_event_name!r} (valid: {valid})"
        ) from exc


def parse_payload(raw: str | dict[str, Any]) -> HookPayload:
    """Parse a stdin JSON payload from Claude Code into a typed payload.

    Accepts either the raw JSON string or an already-decoded dict. Raises
    :class:`ValueError` on malformed input.
    """

    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"hook payload is not valid JSON: {exc}") from exc
    else:
        data = raw
    if not isinstance(data, dict):
        raise ValueError(f"hook payload must be a JSON object, got {type(data).__name__}")
    hook_event_name = _require_str(data, "hook_event_name")
    common = _common_fields(data, hook_event_name)
    if hook_event_name == "SessionStart":
        return SessionStartPayload(
            **common,
            source=_optional_str(data, "source"),
            model=_optional_str(data, "model"),
            agent_type=_optional_str(data, "agent_type"),
        )
    if hook_event_name == "UserPromptSubmit":
        prompt = data.get("prompt", "")
        if prompt is None:
            prompt = ""
        return UserPromptPayload(**common, prompt=str(prompt))
    if hook_event_name == "PreToolUse":
        return PreToolPayload(
            **common,
            tool_name=_require_str(data, "tool_name"),
            tool_input=_dict_field(data, "tool_input"),
            tool_use_id=_optional_str(data, "tool_use_id"),
        )
    if hook_event_name == "PostToolUse":
        return PostToolPayload(
            **common,
            tool_name=_require_str(data, "tool_name"),
            tool_input=_dict_field(data, "tool_input"),
            tool_response=_dict_field(data, "tool_response"),
            tool_use_id=_optional_str(data, "tool_use_id"),
            duration_ms=_optional_int(data, "duration_ms"),
        )
    if hook_event_name == "Stop":
        return SessionEndPayload(
            **common,
            exit_reason=_optional_str(data, "exit_reason"),
            total_cost_usd=_float_field(data, "total_cost_usd"),
            total_tokens_in=_int_field(data, "total_tokens_in"),
            total_tokens_out=_int_field(data, "total_tokens_out"),
            total_events=_int_field(data, "total_events"),
        )
    raise ValueError(f"no parser registered for {hook_event_name!r}")


def _common_fields(data: dict[str, Any], hook_event_name: str) -> dict[str, Any]:
    return {
        "session_id": _require_str(data, "session_id"),
        "transcript_path": _optional_str(data, "transcript_path"),
        "cwd": _require_str(data, "cwd"),
        "permission_mode": _optional_str(data, "permission_mode"),
        "hook_event_name": hook_event_name,
    }


def _require_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing or empty required string field {key!r}")
    return value


def _optional_str(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    return str(value)


def _optional_int(data: dict[str, Any], key: str) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_field(data: dict[str, Any], key: str) -> int:
    value = data.get(key, 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _float_field(data: dict[str, Any], key: str) -> float:
    value = data.get(key, 0.0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _dict_field(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key, {})
    if not isinstance(value, dict):
        return {}
    return dict(value)
