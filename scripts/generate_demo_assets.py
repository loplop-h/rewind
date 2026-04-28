"""Generate marketing assets for the rewind launch.

Outputs (under ``docs/images/``):

* ``hero.png`` — high-resolution still of the TUI timeline at the moment
  the user spots the offending tool call. The single most important asset
  for HN / Reddit / LinkedIn.
* ``rollback.gif`` — short 8-12 second loop showing ``rewind goto`` and
  ``rewind undo`` doing their thing.

The demo is built deterministically from a fixture session so it can be
regenerated on demand and replays the same flow. No external dependencies
beyond Pillow and imageio (already in the project's optional ``[export]``
extra).
"""

from __future__ import annotations

import io
import sys
from dataclasses import dataclass, field
from pathlib import Path

import imageio.v2 as imageio
from PIL import Image, ImageDraw, ImageFont

# Paths -----------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = REPO_ROOT / "docs" / "images"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

CONSOLA_REGULAR = r"C:\Windows\Fonts\consola.ttf"
CONSOLA_BOLD = r"C:\Windows\Fonts\consolab.ttf"


# Palette ---------------------------------------------------------------

class Color:
    BG = "#0d1117"          # GitHub dark
    FG = "#c9d1d9"          # default text
    DIM = "#8b949e"         # secondary text / borders
    BORDER = "#30363d"
    RED = "#f85149"
    GREEN = "#3fb950"
    YELLOW = "#d29922"
    BLUE = "#58a6ff"
    MAGENTA = "#bc8cff"
    CYAN = "#39c5cf"


# Fonts -----------------------------------------------------------------

FONT_SIZE = 18
LINE_HEIGHT = 24
PAD_X = 32
PAD_Y = 28


def load_fonts() -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    return (
        ImageFont.truetype(CONSOLA_REGULAR, FONT_SIZE),
        ImageFont.truetype(CONSOLA_BOLD, FONT_SIZE),
    )


# Span model ------------------------------------------------------------

@dataclass(frozen=True)
class Span:
    text: str
    color: str = Color.FG
    bold: bool = False


@dataclass
class Line:
    spans: list[Span] = field(default_factory=list)

    def add(self, text: str, color: str = Color.FG, bold: bool = False) -> "Line":
        self.spans.append(Span(text=text, color=color, bold=bold))
        return self


def render_lines(
    lines: list[Line],
    *,
    width: int,
    height: int,
) -> Image.Image:
    """Render a list of styled lines to a PIL image."""

    img = Image.new("RGB", (width, height), Color.BG)
    draw = ImageDraw.Draw(img)
    regular, bold = load_fonts()
    y = PAD_Y
    for line in lines:
        x = PAD_X
        for span in line.spans:
            font = bold if span.bold else regular
            draw.text((x, y), span.text, font=font, fill=span.color)
            bbox = draw.textbbox((x, y), span.text, font=font)
            x = bbox[2]
        y += LINE_HEIGHT
    return img


# Hero PNG content ------------------------------------------------------

def hero_lines() -> list[Line]:
    """The 'aha' moment: a populated timeline with one wasted tool call."""

    lines: list[Line] = []
    # Title bar.
    lines.append(
        Line()
        .add("$ ", Color.GREEN, bold=True)
        .add("rewind tui", Color.FG, bold=True)
    )
    lines.append(Line())
    lines.append(
        Line().add("                       rewind  ·  session 7f3a-2b12c4af", Color.MAGENTA, bold=True)
    )
    lines.append(Line())
    # Header.
    lines.append(
        Line()
        .add(" #   time      kind            tool         status        summary", Color.CYAN, bold=True)
    )
    lines.append(
        Line().add(" " + "─" * 96, Color.BORDER)
    )
    # Rows.
    rows = [
        (" 1", "14:32:01", "session_start", "",          "",            "model=claude-opus-4-7"),
        (" 2", "14:32:08", "user_prompt",   "",          "",            'add JWT auth to /login'),
        (" 3", "14:32:14", "pre_tool",      "Edit",      "",            "file_path=auth.py"),
        (" 4", "14:32:14", "post_tool",     "Edit",      "productive",  "success=true"),
        (" 5", "14:32:21", "pre_tool",      "Bash",      "",            "command=pytest -q"),
        (" 6", "14:32:23", "post_tool",     "Bash",      "wasted",      "exit_code=1   ← agent broke things"),
        (" 7", "14:32:30", "pre_tool",      "Read",      "",            "file_path=auth.py"),
        (" 8", "14:32:30", "post_tool",     "Read",      "neutral",     "bytes=482"),
        (" 9", "14:32:38", "pre_tool",      "Edit",      "",            "file_path=auth.py"),
        ("10", "14:32:38", "post_tool",     "Edit",      "productive",  "success=true"),
        ("11", "14:32:44", "pre_tool",      "Bash",      "",            "command=pytest -q"),
        ("12", "14:32:46", "post_tool",     "Bash",      "productive",  "exit_code=0   passed in 1.42s"),
    ]
    kind_color = {
        "session_start": Color.GREEN,
        "user_prompt": Color.BLUE,
        "pre_tool": Color.YELLOW,
        "post_tool": Color.CYAN,
        "session_end": Color.RED,
    }
    status_color = {
        "productive": Color.GREEN,
        "wasted": Color.RED,
        "neutral": Color.DIM,
        "": Color.FG,
    }
    for n, t, kind, tool, status, summary in rows:
        line = Line()
        line.add(f" {n}", Color.DIM)
        line.add(f"  {t}", Color.DIM)
        line.add(f"  {kind:<14}", kind_color[kind], bold=True)
        line.add(f" {tool:<11}", Color.FG)
        line.add(f" {status:<13}", status_color[status], bold=bool(status))
        sum_color = Color.RED if "broke" in summary else Color.FG
        line.add(f" {summary}", sum_color, bold="broke" in summary)
        lines.append(line)

    lines.append(Line())
    lines.append(
        Line()
        .add("12 events  ·  ", Color.DIM)
        .add("$0.04  ", Color.GREEN)
        .add("·  4 tool calls  ·  ", Color.DIM)
        .add("75% productive  ", Color.GREEN, bold=True)
        .add("·  ", Color.DIM)
        .add("8% wasted", Color.RED, bold=True)
    )
    lines.append(Line())
    lines.append(
        Line()
        .add("press ", Color.DIM)
        .add("g", Color.YELLOW, bold=True)
        .add(" + seq to rollback", Color.DIM)
        .add("    ·    ", Color.BORDER)
        .add("e", Color.YELLOW, bold=True)
        .add(" to export", Color.DIM)
        .add("    ·    ", Color.BORDER)
        .add("/", Color.YELLOW, bold=True)
        .add(" to search", Color.DIM)
    )
    return lines


def build_hero_png() -> Path:
    img = render_lines(hero_lines(), width=1240, height=520)
    out = ASSETS_DIR / "hero.png"
    img.save(out, optimize=True)
    return out


# Rollback GIF frames ---------------------------------------------------

def rollback_frames() -> list[tuple[float, list[Line]]]:
    """Return (duration_seconds, lines) tuples building up the rollback story."""

    frames: list[tuple[float, list[Line]]] = []

    base: list[Line] = []
    base.append(
        Line()
        .add("$ ", Color.GREEN, bold=True)
        .add("rewind tui", Color.FG, bold=True)
    )
    base.append(Line())
    base.append(
        Line().add(" 5  14:32:21  pre_tool       Bash         ", Color.YELLOW)
        .add("            command=pytest -q", Color.FG)
    )
    base.append(
        Line().add(" 6  14:32:23  post_tool      Bash         ", Color.CYAN)
        .add("wasted        ", Color.RED, bold=True)
        .add("exit_code=1  ← agent broke things", Color.RED, bold=True)
    )
    base.append(
        Line().add(" 7  14:32:30  pre_tool       Read         ", Color.YELLOW)
        .add("            file_path=auth.py", Color.FG)
    )
    base.append(Line())
    frames.append((1.6, base))

    # Goto command typed.
    after_goto_typed: list[Line] = list(base) + [
        Line()
        .add("$ ", Color.GREEN, bold=True)
        .add("rewind goto 5", Color.FG, bold=True)
    ]
    frames.append((1.0, after_goto_typed))

    # Goto output.
    after_goto: list[Line] = list(after_goto_typed) + [
        Line().add("plan: 1 restore, 0 delete, 0 unchanged (target seq=5)", Color.FG),
        Line().add("  ", Color.FG).add("restore  ", Color.GREEN, bold=True).add("/repo/auth.py", Color.FG),
        Line().add("rolled back. checkpoint id: 1777384392012-7f3a", Color.GREEN, bold=True),
    ]
    frames.append((2.0, after_goto))

    # Undo command typed.
    after_undo_typed: list[Line] = list(after_goto) + [
        Line(),
        Line()
        .add("$ ", Color.GREEN, bold=True)
        .add("rewind undo", Color.FG, bold=True),
    ]
    frames.append((1.0, after_undo_typed))

    # Undo output.
    after_undo: list[Line] = list(after_undo_typed) + [
        Line().add("undone checkpoint 1777384392012-7f3a: 1 restored, 0 deleted", Color.GREEN, bold=True),
    ]
    frames.append((2.0, after_undo))

    # Final card.
    final: list[Line] = [
        Line(),
        Line().add("rewind v0.1.0", Color.MAGENTA, bold=True),
        Line(),
        Line().add("$ ", Color.GREEN, bold=True).add("pip install rewindx", Color.FG, bold=True),
        Line().add("$ ", Color.GREEN, bold=True).add("rewind cc setup", Color.FG, bold=True),
        Line(),
        Line().add("github.com/loplop-h/rewind", Color.BLUE, bold=True),
    ]
    frames.append((2.6, final))

    return frames


def build_rollback_gif() -> Path:
    width, height = 1100, 380
    fps = 10
    images: list[Image.Image] = []
    durations: list[int] = []
    for seconds, lines in rollback_frames():
        frame = render_lines(lines, width=width, height=height)
        n = max(1, int(seconds * fps))
        for _ in range(n):
            images.append(frame)
        durations.extend([int(1000 / fps)] * n)

    out = ASSETS_DIR / "rollback.gif"
    # imageio writes per-frame durations from the durations kwarg.
    imageio.mimsave(
        out,
        [im for im in images],
        duration=durations,
        loop=0,
        subrectangles=True,
    )
    return out


# Entry point -----------------------------------------------------------


def main() -> int:
    print("[hero] generating PNG…", flush=True)
    hero = build_hero_png()
    print(f"[hero] wrote {hero}  ({hero.stat().st_size / 1024:.1f} KB)")
    print("[gif]  generating rollback GIF…", flush=True)
    gif = build_rollback_gif()
    print(f"[gif]  wrote {gif}  ({gif.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
