"""Unified-diff rendering for file snapshot pairs."""

from __future__ import annotations

import difflib
from collections.abc import Iterable

from rich.text import Text


def build_unified_diff(
    *,
    before_text: str,
    after_text: str,
    path: str,
    context_lines: int = 3,
) -> Text:
    """Return a colourised unified diff suitable for printing in the TUI."""

    before_lines = before_text.splitlines(keepends=True)
    after_lines = after_text.splitlines(keepends=True)
    raw_diff = difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        n=context_lines,
    )
    return _colour_diff(raw_diff)


def _colour_diff(lines: Iterable[str]) -> Text:
    out = Text()
    for line in lines:
        if line.startswith("+++") or line.startswith("---"):
            out.append(line, style="bold")
        elif line.startswith("@@"):
            out.append(line, style="cyan")
        elif line.startswith("+"):
            out.append(line, style="green")
        elif line.startswith("-"):
            out.append(line, style="red")
        else:
            out.append(line)
    return out


def safe_decode(content: bytes) -> str:
    """Return ``content`` as text. Replaces invalid bytes with U+FFFD."""

    return content.decode("utf-8", errors="replace")
