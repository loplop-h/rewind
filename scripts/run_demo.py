"""Demo runner — types each command with a typewriter effect and runs it.

Designed to be screen-recorded with OBS. Run after ``scripts/prep_demo.py``
has seeded ``$REWIND_DEMO_HOME`` and ``$REWIND_DEMO_PROJECT``.

The runner pauses between actions so the watcher (a) can read the output
and (b) gets a clear "narrative beat" between scenes.

The output is the *real* ``rewind`` CLI talking to the *real* SQLite
session that ``prep_demo.py`` seeded. There is no fakery here, only
deterministic timing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROMPT_USER = "\033[1;32m$\033[0m "
PROMPT_NOTE = "\033[2;37m# \033[0m"
TYPE_DELAY = 0.04
PAUSE_AFTER_OUTPUT = 1.6
PAUSE_BETWEEN_ACTS = 2.2


def typewrite(text: str, delay: float = TYPE_DELAY) -> None:
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write("\n")
    sys.stdout.flush()


def run_cmd(cmd: list[str], env: dict[str, str]) -> int:
    return subprocess.call(cmd, env=env)


def banner(text: str) -> None:
    sys.stdout.write("\n")
    sys.stdout.write(f"\033[1;35m{text}\033[0m")
    sys.stdout.write("\n\n")
    sys.stdout.flush()


def beat(seconds: float = PAUSE_AFTER_OUTPUT) -> None:
    time.sleep(seconds)


def main() -> int:
    rewind_home = os.environ.get("REWIND_DEMO_HOME") or str(Path.home() / "rewind-demo-home")
    project = os.environ.get("REWIND_DEMO_PROJECT") or str(Path.home() / "rewind-demo-project")
    rewind_bin = shutil.which("rewind")
    if rewind_bin is None:
        print("rewind binary not on PATH (try `pip install rewindx` first)", file=sys.stderr)
        return 2
    if not Path(rewind_home).exists() or not Path(project).exists():
        print("Demo state missing. Run `python scripts/prep_demo.py` first.", file=sys.stderr)
        return 2

    env = {**os.environ, "REWIND_HOME": rewind_home}
    auth = str(Path(project) / "auth.py")

    # Clear the screen first.
    os.system("cls" if os.name == "nt" else "clear")
    time.sleep(0.6)

    banner("ACT 1 — what does the agent see?")
    sys.stdout.write(PROMPT_USER)
    typewrite("rewind tui demo-7f3a-2b12c4af")
    run_cmd([rewind_bin, "tui", "demo-7f3a-2b12c4af"], env)
    beat(2.4)

    banner("ACT 2 — agent broke things at seq 6. Roll back to seq 5.")
    sys.stdout.write(PROMPT_USER)
    typewrite(f"cat {auth}")
    run_cmd(["cat", auth], env) if os.name != "nt" else subprocess.call(
        ["type", auth], env=env, shell=True
    )
    beat()

    sys.stdout.write(PROMPT_USER)
    typewrite(f"rewind goto 5 --session demo-7f3a-2b12c4af --cwd {project}")
    run_cmd(
        [
            rewind_bin,
            "goto",
            "5",
            "--session",
            "demo-7f3a-2b12c4af",
            "--cwd",
            project,
        ],
        env,
    )
    beat()

    sys.stdout.write(PROMPT_USER)
    typewrite(f"cat {auth}")
    run_cmd(["cat", auth], env) if os.name != "nt" else subprocess.call(
        ["type", auth], env=env, shell=True
    )
    beat(PAUSE_BETWEEN_ACTS)

    banner("ACT 3 — undo the rollback. Back to where we were.")
    sys.stdout.write(PROMPT_USER)
    typewrite("rewind undo")
    run_cmd([rewind_bin, "undo"], env)
    beat()

    sys.stdout.write(PROMPT_USER)
    typewrite(f"cat {auth}")
    run_cmd(["cat", auth], env) if os.name != "nt" else subprocess.call(
        ["type", auth], env=env, shell=True
    )
    beat(PAUSE_BETWEEN_ACTS)

    banner("ACT 4 — share the session.")
    sys.stdout.write(PROMPT_USER)
    typewrite("rewind export demo-7f3a-2b12c4af --format markdown")
    ps = subprocess.run(
        [rewind_bin, "export", "demo-7f3a-2b12c4af", "--format", "markdown"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    # Cap rendered preview at ~26 lines so the markdown fits comfortably
    # in the recording without scrolling the title card off-screen.
    for line in ps.stdout.splitlines()[:26]:
        sys.stdout.write(line + "\n")
    sys.stdout.write("...\n")
    sys.stdout.flush()
    beat(PAUSE_BETWEEN_ACTS)

    banner("rewind v0.1.2  ·  pip install rewindx  ·  github.com/loplop-h/rewind")
    beat(2.5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
