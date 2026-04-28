"""Static timeline rendering. Used by both the live TUI and ``rewind tui`` snapshot mode."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime

from rich.table import Table
from rich.text import Text

from rewind.store.models import Event, EventKind, ToolStatus


def build_timeline_table(events: Iterable[Event], *, title: str | None = None) -> Table:
    """Return a Rich :class:`Table` rendering the event timeline."""

    table = Table(
        title=title,
        show_lines=False,
        header_style="bold cyan",
        title_style="bold",
    )
    table.add_column("#", justify="right", style="dim", no_wrap=True)
    table.add_column("time", justify="left", style="dim", no_wrap=True)
    table.add_column("kind", justify="left", no_wrap=True)
    table.add_column("tool", justify="left", no_wrap=True)
    table.add_column("status", justify="left", no_wrap=True)
    table.add_column("summary", justify="left", overflow="fold")
    for ev in events:
        table.add_row(
            str(ev.seq),
            _fmt_time(ev.ts),
            _fmt_kind(ev.kind),
            ev.tool_name or "",
            _fmt_status(ev.tool_status),
            _summarise(ev),
        )
    return table


def _fmt_time(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=UTC).strftime("%H:%M:%S")


def _fmt_kind(kind: EventKind) -> Text:
    palette = {
        EventKind.SESSION_START: "bold green",
        EventKind.USER_PROMPT: "bold blue",
        EventKind.PRE_TOOL: "yellow",
        EventKind.POST_TOOL: "cyan",
        EventKind.SESSION_END: "bold red",
    }
    return Text(kind.value, style=palette.get(kind, ""))


def _fmt_status(status: ToolStatus | None) -> Text:
    if status is None:
        return Text("")
    palette = {
        ToolStatus.PRODUCTIVE: "bold green",
        ToolStatus.WASTED: "bold red",
        ToolStatus.NEUTRAL: "dim",
    }
    return Text(status.value, style=palette[status])


def _summarise(ev: Event) -> str:
    if ev.kind is EventKind.USER_PROMPT and ev.tool_input_json:
        try:
            data = json.loads(ev.tool_input_json)
        except json.JSONDecodeError:
            data = {}
        prompt = str(data.get("prompt", "")).replace("\n", " ").strip()
        return _ellipsis(prompt, 80)
    if ev.tool_input_json:
        try:
            data = json.loads(ev.tool_input_json)
        except json.JSONDecodeError:
            data = {}
        for key in ("file_path", "command", "pattern", "url", "description"):
            value = data.get(key)
            if isinstance(value, str) and value:
                return _ellipsis(f"{key}={value}", 80)
        return _ellipsis(str(data), 80)
    return ""


def _ellipsis(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"
