"""End-to-end smoke test of the PyPI-installed rewindx wheel.

Run with the rewindx wheel pre-installed in the *current* Python
environment. The script provisions a clean REWIND_HOME, simulates a tiny
Claude Code session via ``rewind capture``, then runs the full lifecycle
(``sessions list``, ``stats``, ``goto``, ``undo``) and asserts each step.

Exits 0 on success, non-zero on any failure.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def cap(rewind: str, kind: str, payload: dict, env: dict) -> None:
    p = subprocess.run(
        [rewind, "capture", kind],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=20,
        env=env,
    )
    if p.returncode != 0:
        raise RuntimeError(f"capture {kind} failed: rc={p.returncode} stderr={p.stderr!r}")


def run(rewind: str, *args: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [rewind, *args],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def main() -> int:
    rewind = shutil.which("rewind")
    if rewind is None:
        print("rewind binary not on PATH", file=sys.stderr)
        return 2

    workdir = Path(tempfile.mkdtemp(prefix="rewindx-smoke-"))
    try:
        proj = workdir / "proj"
        proj.mkdir()
        target = proj / "x.py"
        target.write_text("def hello():\n    return 1\n", encoding="utf-8")

        rewind_home = workdir / "rh"
        env = {**os.environ, "REWIND_HOME": str(rewind_home)}

        sid = "smoke-1"
        common = {
            "session_id": sid,
            "transcript_path": "t",
            "cwd": str(proj),
            "permission_mode": "default",
        }
        cap(
            rewind,
            "session-start",
            {**common, "hook_event_name": "SessionStart", "source": "startup", "model": "opus"},
            env,
        )
        cap(
            rewind,
            "user-prompt",
            {**common, "hook_event_name": "UserPromptSubmit", "prompt": "rename hello to greet"},
            env,
        )
        cap(
            rewind,
            "pre-tool",
            {
                **common,
                "hook_event_name": "PreToolUse",
                "tool_name": "Edit",
                "tool_input": {"file_path": str(target)},
            },
            env,
        )
        target.write_text("def greet():\n    return 1\n", encoding="utf-8")
        cap(
            rewind,
            "post-tool",
            {
                **common,
                "hook_event_name": "PostToolUse",
                "tool_name": "Edit",
                "tool_input": {"file_path": str(target)},
                "tool_response": {"success": True},
                "duration_ms": 5,
            },
            env,
        )
        cap(
            rewind,
            "session-end",
            {
                **common,
                "hook_event_name": "Stop",
                "exit_reason": "normal",
                "total_cost_usd": 0.05,
                "total_events": 4,
            },
            env,
        )

        ls = run(rewind, "sessions", "list", env=env)
        assert sid in ls.stdout, f"session not listed: {ls.stdout!r}"
        print("[ok] sessions list contains", sid)

        stats = run(rewind, "stats", "--json", env=env)
        parsed = json.loads(stats.stdout)
        assert parsed["session_id"] == sid
        print("[ok] stats parsed", parsed["event_count"], "events")

        goto = run(rewind, "goto", "4", "--session", sid, "--cwd", str(proj), env=env)
        assert "rolled back" in goto.stdout.lower(), f"goto output: {goto.stdout!r}"
        assert target.read_text(encoding="utf-8").strip() == "def hello():\n    return 1".strip()
        print("[ok] goto restored file")

        undo = run(rewind, "undo", env=env)
        assert "undone" in undo.stdout.lower(), f"undo output: {undo.stdout!r}"
        assert "greet" in target.read_text(encoding="utf-8")
        print("[ok] undo restored greet")

        export = run(rewind, "export", "--format", "markdown", env=env)
        assert "rewind" in export.stdout.lower()
        print("[ok] export rendered markdown")

        print("\nALL SMOKE CHECKS PASSED")
        return 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
