"""Frame model + text/markdown renderers for session export.

A :class:`Frame` is a self-contained snapshot of one moment in the session
(title card, prompt, tool call, edit, summary). The renderers turn a list of
frames into shareable text/markdown. The optional GIF backend (gated behind
the ``export`` extra) consumes the same frames.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from rewind.export.privacy import mask_text
from rewind.store.models import Event, EventKind, Session, ToolStatus


class FrameKind(StrEnum):
    TITLE = "title"
    PROMPT = "prompt"
    TOOL = "tool"
    EDIT = "edit"
    SUMMARY = "summary"


@dataclass(frozen=True, slots=True, kw_only=True)
class Frame:
    """One renderable moment in the export."""

    seq: int
    kind: FrameKind
    title: str
    body: str = ""
    meta: dict[str, str] = field(default_factory=dict)


def build_frames(
    *,
    session: Session,
    events: Iterable[Event],
    mask: bool = True,
) -> list[Frame]:
    """Translate ``(session, events)`` into a sequence of frames suitable for export."""

    frames: list[Frame] = [
        Frame(
            seq=0,
            kind=FrameKind.TITLE,
            title=f"rewind · session {session.id[:12]}",
            body=_format_session_header(session),
            meta={"started_at": _fmt_ts(session.started_at)},
        )
    ]
    for ev in events:
        frame = _frame_from_event(ev, mask=mask)
        if frame is not None:
            frames.append(frame)
    frames.append(
        Frame(
            seq=len(frames),
            kind=FrameKind.SUMMARY,
            title="summary",
            body=_format_session_summary(session),
            meta={
                "ended_at": _fmt_ts(session.ended_at) if session.ended_at else "",
            },
        )
    )
    return frames


def render_text(frames: Iterable[Frame]) -> str:
    """Render frames as a plain-text transcript."""

    out: list[str] = []
    for f in frames:
        head = f"[{f.seq:03d}] {f.kind.value.upper():<8} · {f.title}"
        out.append(head)
        if f.body:
            out.append(_indent(f.body, 4))
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def render_markdown(frames: Iterable[Frame], *, session: Session | None = None) -> str:
    """Render frames as a Markdown transcript (good for PR descriptions, gists, blog posts)."""

    out: list[str] = []
    if session is not None:
        out.append(f"# rewind · session {session.id[:12]}\n")
        out.append(f"*started {_fmt_ts(session.started_at)} · cwd `{session.cwd}`*\n\n---\n")
    for f in frames:
        out.append(f"## {f.kind.value.title()} · {f.title}")
        if f.body:
            if f.kind in (FrameKind.TOOL, FrameKind.EDIT):
                out.append(f"\n```\n{f.body.rstrip()}\n```\n")
            else:
                out.append(f"\n{f.body}\n")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def _frame_from_event(ev: Event, *, mask: bool) -> Frame | None:
    if ev.kind is EventKind.SESSION_START:
        return Frame(
            seq=ev.seq,
            kind=FrameKind.TITLE,
            title="session started",
            body=ev.model or "",
            meta={"ts": _fmt_ts(ev.ts)},
        )
    if ev.kind is EventKind.USER_PROMPT:
        body = _user_prompt_body(ev, mask=mask)
        return Frame(
            seq=ev.seq,
            kind=FrameKind.PROMPT,
            title="user prompt",
            body=body,
            meta={"ts": _fmt_ts(ev.ts)},
        )
    if ev.kind is EventKind.POST_TOOL:
        return _tool_frame(ev, mask=mask)
    if ev.kind is EventKind.SESSION_END:
        return None
    return None


def _user_prompt_body(ev: Event, *, mask: bool) -> str:
    if not ev.tool_input_json:
        return ""
    try:
        data = json.loads(ev.tool_input_json)
    except json.JSONDecodeError:
        return ""
    text = str(data.get("prompt", ""))
    return mask_text(text) if mask else text


def _tool_frame(ev: Event, *, mask: bool) -> Frame:
    body = _summarise_tool_output(ev, mask=mask)
    is_edit = ev.tool_name in {"Write", "Edit", "MultiEdit", "NotebookEdit"}
    kind = FrameKind.EDIT if is_edit else FrameKind.TOOL
    return Frame(
        seq=ev.seq,
        kind=kind,
        title=f"{ev.tool_name or 'tool'} · {_status_label(ev.tool_status)}",
        body=body,
        meta={
            "ts": _fmt_ts(ev.ts),
            "duration_ms": str(ev.duration_ms or 0),
        },
    )


def _summarise_tool_output(ev: Event, *, mask: bool) -> str:
    if not ev.tool_input_json and not ev.tool_output_json:
        return ""
    parts: list[str] = []
    if ev.tool_input_json:
        try:
            input_data = json.loads(ev.tool_input_json)
        except json.JSONDecodeError:
            input_data = {}
        parts.append("input: " + _shorten_obj(input_data, mask=mask))
    if ev.tool_output_json:
        try:
            output_data = json.loads(ev.tool_output_json)
        except json.JSONDecodeError:
            output_data = {}
        parts.append("output: " + _shorten_obj(output_data, mask=mask))
    return "\n".join(parts)


def _shorten_obj(obj: Any, *, mask: bool) -> str:
    serialised = json.dumps(obj, default=str)
    if mask:
        serialised = mask_text(serialised, head=4, tail=4)
    if len(serialised) > 800:
        return serialised[:797] + "..."
    return serialised


def _format_session_header(session: Session) -> str:
    return (
        f"cwd: {session.cwd}\n"
        f"model: {session.model or '(unset)'}\n"
        f"started: {_fmt_ts(session.started_at)}"
    )


def _format_session_summary(session: Session) -> str:
    lines = [
        f"events: {session.total_events}",
        f"cost: ${session.total_cost_usd:.2f}",
        f"tokens in/out: {session.total_tokens_in}/{session.total_tokens_out}",
    ]
    if session.exit_reason:
        lines.append(f"exit: {session.exit_reason}")
    return "\n".join(lines)


def _fmt_ts(ts_ms: int | None) -> str:
    if ts_ms is None:
        return ""
    return datetime.fromtimestamp(ts_ms / 1000, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _status_label(status: ToolStatus | None) -> str:
    return status.value if status else "neutral"


def _indent(text: str, n: int) -> str:
    pad = " " * n
    return "\n".join(pad + line if line else line for line in text.splitlines())
