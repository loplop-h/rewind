"""Privacy filters for session exports.

Masks file contents to first/last N lines and redacts environment-variable
shaped tokens. Default-on; the caller is expected to pass ``--no-mask`` (or
the equivalent flag) before building unmasked frames.
"""

from __future__ import annotations

import re

ENV_PATTERN = re.compile(
    r"""
    \b(
        [A-Z][A-Z0-9_]{2,}_(?:KEY|TOKEN|SECRET|PASS|PASSWORD|API|AUTH|HASH)
        |API[_-]?KEY
        |AUTH[_-]?TOKEN
    )\b\s*[:=]\s*['"]?([^\s'"]{4,})['"]?
    """,
    re.VERBOSE,
)


REDACTED = "<redacted>"


def mask_text(content: str, *, head: int = 8, tail: int = 8) -> str:
    """Truncate to ``head`` + ``tail`` lines and scrub env-shaped secrets.

    If the content has fewer than ``head + tail + 1`` lines, return it
    in full (still scrubbed). Otherwise insert a marker between the head
    and tail.
    """

    if not content:
        return content
    redacted = ENV_PATTERN.sub(lambda m: f"{m.group(1)}={REDACTED}", content)
    lines = redacted.splitlines()
    if len(lines) <= head + tail + 1:
        return redacted
    elided = len(lines) - head - tail
    return "\n".join(
        [
            *lines[:head],
            f"... <{elided} lines elided> ...",
            *lines[-tail:],
        ]
    )


def is_sensitive_path(path: str) -> bool:
    """Heuristic check used by the export to skip sensitive files entirely."""

    lowered = path.lower()
    sensitive = (
        ".env",
        ".pem",
        ".key",
        "id_rsa",
        ".aws/credentials",
        ".npmrc",
        ".pypirc",
    )
    return any(lowered.endswith(s) or s in lowered for s in sensitive)
