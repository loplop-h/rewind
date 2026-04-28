"""Tests for the export pipeline."""

from __future__ import annotations

from rewind.export import (
    Frame,
    build_frames,
    mask_text,
    render_markdown,
    render_text,
)
from rewind.export.frames import FrameKind
from rewind.export.privacy import is_sensitive_path
from rewind.store.models import Event, EventKind, Session, ToolStatus


def _events_for(session_id: str) -> list[Event]:
    return [
        Event(session_id=session_id, seq=1, ts=1, kind=EventKind.SESSION_START, model="opus"),
        Event(
            session_id=session_id,
            seq=2,
            ts=2,
            kind=EventKind.USER_PROMPT,
            tool_input_json='{"prompt":"do the thing"}',
        ),
        Event(
            session_id=session_id,
            seq=3,
            ts=3,
            kind=EventKind.POST_TOOL,
            tool_name="Edit",
            tool_status=ToolStatus.PRODUCTIVE,
            tool_input_json='{"file_path":"/tmp/x.py"}',
            tool_output_json='{"success":true}',
        ),
        Event(
            session_id=session_id,
            seq=4,
            ts=4,
            kind=EventKind.SESSION_END,
        ),
    ]


def test_build_frames_includes_title_and_summary() -> None:
    session = Session(id="s1", started_at=0, cwd="/x", model="opus")
    frames = build_frames(session=session, events=_events_for("s1"))
    kinds = [f.kind for f in frames]
    assert kinds[0] is FrameKind.TITLE
    assert kinds[-1] is FrameKind.SUMMARY


def test_render_text_contains_prompt_and_tool() -> None:
    session = Session(id="s1", started_at=0, cwd="/x")
    frames = build_frames(session=session, events=_events_for("s1"))
    text = render_text(frames)
    assert "PROMPT" in text
    assert "TOOL" in text or "EDIT" in text
    assert "do the thing" in text


def test_render_markdown_uses_code_fences_for_tools() -> None:
    session = Session(id="s1", started_at=0, cwd="/x")
    frames = build_frames(session=session, events=_events_for("s1"))
    md = render_markdown(frames, session=session)
    assert "```" in md
    assert "## " in md


def test_mask_text_truncates_long_content() -> None:
    big = "\n".join(f"line {i}" for i in range(1, 100))
    masked = mask_text(big, head=3, tail=3)
    assert "lines elided" in masked
    assert masked.startswith("line 1")
    assert masked.endswith("line 99")


def test_mask_text_redacts_secret_shaped_values() -> None:
    sample = "AWS_SECRET_KEY=AKIA123456789ABCDEF"
    masked = mask_text(sample)
    assert "AKIA123456789ABCDEF" not in masked


def test_mask_text_short_content_unchanged() -> None:
    assert mask_text("hi") == "hi"


def test_is_sensitive_path() -> None:
    assert is_sensitive_path("/x/.env")
    assert is_sensitive_path("/y/id_rsa")
    assert is_sensitive_path("/x/.aws/credentials")
    assert not is_sensitive_path("/x/src/main.py")


def test_frame_dataclass_round_trip() -> None:
    f = Frame(seq=1, kind=FrameKind.PROMPT, title="t", body="b", meta={"k": "v"})
    assert f.title == "t"
    assert f.meta["k"] == "v"
