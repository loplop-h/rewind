"""Capture pipeline: parse Claude Code hook payloads into events + snapshots."""

from rewind.capture.hooks import HookHandler, ingest_payload
from rewind.capture.payload import (
    HookPayload,
    PostToolPayload,
    PreToolPayload,
    SessionEndPayload,
    SessionStartPayload,
    UserPromptPayload,
    parse_payload,
)
from rewind.capture.snapshot import (
    classify_tool_call,
    extract_paths_from_tool_input,
    record_post_tool_snapshot,
    record_pre_tool_snapshot,
)

__all__ = [
    "HookHandler",
    "HookPayload",
    "PostToolPayload",
    "PreToolPayload",
    "SessionEndPayload",
    "SessionStartPayload",
    "UserPromptPayload",
    "classify_tool_call",
    "extract_paths_from_tool_input",
    "ingest_payload",
    "parse_payload",
    "record_post_tool_snapshot",
    "record_pre_tool_snapshot",
]
