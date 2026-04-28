"""Shareable session export.

V1 implements a text-frame builder and a markdown export. GIF/MP4 frame
rendering is gated behind the optional ``[export]`` extra and the lower-level
:func:`render_frames_to_gif` helper, so the core install stays light.
"""

from rewind.export.frames import (
    Frame,
    build_frames,
    render_markdown,
    render_text,
)
from rewind.export.privacy import mask_text

__all__ = [
    "Frame",
    "build_frames",
    "mask_text",
    "render_markdown",
    "render_text",
]
