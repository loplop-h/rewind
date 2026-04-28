"""Rich-based TUI for browsing a rewind session."""

from rewind.tui.app import render_session, run_tui
from rewind.tui.diff import build_unified_diff
from rewind.tui.timeline import build_timeline_table

__all__ = [
    "build_timeline_table",
    "build_unified_diff",
    "render_session",
    "run_tui",
]
