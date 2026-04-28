"""Seed a synthetic rewind session under a custom REWIND_HOME for the launch demo.

Creates:

* ``$REWIND_HOME/sessions/demo-7f3a/events.db`` — populated with the same
  12-event story we show in the README hero PNG.
* A dedicated project directory at ``$DEMO_PROJECT`` with one file
  (``auth.py``) at the *broken* "after seq=4" state, so ``rewind goto 5``
  visibly restores it to the working version.

Run once before the demo. Outputs the absolute paths the runner script
needs as environment variables.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from rewind.config import Config  # noqa: E402
from rewind.sessions import SessionManager  # noqa: E402
from rewind.store.models import Event, EventKind, FileSnapshot, Session, ToolStatus  # noqa: E402

SESSION_ID = "demo-7f3a-2b12c4af"


AUTH_OK = """\
import jwt

SECRET = "dev-only-change-me"

def issue_token(user_id: str) -> str:
    return jwt.encode({"sub": user_id}, SECRET, algorithm="HS256")


def verify_token(token: str) -> dict:
    return jwt.decode(token, SECRET, algorithms=["HS256"])
"""

AUTH_BROKEN = """\
import jwt

SECRET = "dev-only-change-me"

def issue_token(user_id: str) -> str:
    # agent removed the algorithm arg accidentally
    return jwt.encode({"sub": user_id}, SECRET)


def verify_token(token):
    return jwt.decode(token, SECRET)
"""


def seed(rewind_home: Path, project: Path) -> None:
    rewind_home.mkdir(parents=True, exist_ok=True)
    project.mkdir(parents=True, exist_ok=True)

    target = project / "auth.py"
    target.write_text(AUTH_OK, encoding="utf-8")

    env = {**os.environ, "REWIND_HOME": str(rewind_home)}
    os.environ["REWIND_HOME"] = str(rewind_home)

    config = Config.from_env(env=env)
    config.ensure_dirs()
    manager = SessionManager(config)
    store, blobs = manager.open_session(SESSION_ID)

    blob_ok = blobs.write_bytes(AUTH_OK.encode("utf-8"))
    blob_broken = blobs.write_bytes(AUTH_BROKEN.encode("utf-8"))

    started_at = int(time.time() * 1000) - (60 * 60 * 1000)
    store.upsert_session(
        Session(
            id=SESSION_ID,
            started_at=started_at,
            cwd=str(project),
            model="claude-opus-4-7",
            total_cost_usd=0.04,
            total_tokens_in=2_481,
            total_tokens_out=1_207,
            total_events=12,
        )
    )

    def _ev(
        seq: int,
        kind: EventKind,
        *,
        tool: str | None = None,
        status: ToolStatus | None = None,
        input_json: str | None = None,
        output_json: str | None = None,
    ) -> int:
        return store.insert_event(
            Event(
                session_id=SESSION_ID,
                seq=seq,
                ts=started_at + seq * 7_000,
                kind=kind,
                tool_name=tool,
                tool_status=status,
                tool_input_json=input_json,
                tool_output_json=output_json,
                duration_ms=12 if kind is EventKind.POST_TOOL else None,
                model="claude-opus-4-7" if kind is EventKind.SESSION_START else None,
            )
        )

    _ev(1, EventKind.SESSION_START)
    _ev(2, EventKind.USER_PROMPT, input_json='{"prompt":"add JWT auth to /login"}')
    pre_id = _ev(
        3, EventKind.PRE_TOOL, tool="Edit", input_json=f'{{"file_path":"{target.as_posix()}"}}'
    )
    store.insert_file_snapshot(
        FileSnapshot(
            event_id=pre_id,
            path=str(target),
            before_hash=None,
            after_hash=blob_broken,
            bytes_before=None,
            bytes_after=len(AUTH_BROKEN.encode("utf-8")),
        )
    )
    _ev(
        4,
        EventKind.POST_TOOL,
        tool="Edit",
        status=ToolStatus.PRODUCTIVE,
        input_json=f'{{"file_path":"{target.as_posix()}"}}',
        output_json='{"success":true}',
    )
    _ev(5, EventKind.PRE_TOOL, tool="Bash", input_json='{"command":"pytest -q"}')
    _ev(
        6,
        EventKind.POST_TOOL,
        tool="Bash",
        status=ToolStatus.WASTED,
        input_json='{"command":"pytest -q"}',
        output_json='{"exit_code":1,"stdout":"FAILED tests/test_auth.py::test_issue_and_verify - jwt.exceptions.DecodeError: not enough segments"}',
    )
    _ev(7, EventKind.PRE_TOOL, tool="Read", input_json=f'{{"file_path":"{target.as_posix()}"}}')
    _ev(
        8,
        EventKind.POST_TOOL,
        tool="Read",
        status=ToolStatus.NEUTRAL,
        input_json=f'{{"file_path":"{target.as_posix()}"}}',
        output_json='{"bytes":482}',
    )
    pre_id_9 = _ev(
        9, EventKind.PRE_TOOL, tool="Edit", input_json=f'{{"file_path":"{target.as_posix()}"}}'
    )
    store.insert_file_snapshot(
        FileSnapshot(
            event_id=pre_id_9,
            path=str(target),
            before_hash=blob_broken,
            after_hash=blob_ok,
            bytes_before=len(AUTH_BROKEN.encode("utf-8")),
            bytes_after=len(AUTH_OK.encode("utf-8")),
        )
    )
    _ev(
        10,
        EventKind.POST_TOOL,
        tool="Edit",
        status=ToolStatus.PRODUCTIVE,
        input_json=f'{{"file_path":"{target.as_posix()}"}}',
        output_json='{"success":true}',
    )
    _ev(11, EventKind.PRE_TOOL, tool="Bash", input_json='{"command":"pytest -q"}')
    _ev(
        12,
        EventKind.POST_TOOL,
        tool="Bash",
        status=ToolStatus.PRODUCTIVE,
        input_json='{"command":"pytest -q"}',
        output_json='{"exit_code":0,"stdout":"passed in 1.42s"}',
    )
    store.close()

    # Now overwrite the on-disk file with the BROKEN content so `rewind goto 5`
    # has something to restore.
    target.write_text(AUTH_BROKEN, encoding="utf-8")


def main() -> int:
    home = Path(os.environ.get("REWIND_DEMO_HOME") or Path.home() / "rewind-demo-home").resolve()
    project = Path(
        os.environ.get("REWIND_DEMO_PROJECT") or Path.home() / "rewind-demo-project"
    ).resolve()
    if home.exists():
        shutil.rmtree(home)
    if project.exists():
        shutil.rmtree(project)
    seed(home, project)
    print("DEMO READY")
    print(f"  REWIND_HOME = {home}")
    print(f"  PROJECT     = {project}")
    print(f"  session id  = {SESSION_ID}")
    print()
    print("Now run:  python scripts/run_demo.py")
    print("(scripts/run_demo.py will print the typewriter commands and exec them)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
