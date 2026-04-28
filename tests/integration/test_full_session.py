"""End-to-end test: ingest a synthetic Claude Code session and exercise rollback."""

from __future__ import annotations

import json
from pathlib import Path

from rewind.capture.hooks import ingest_payload
from rewind.capture.payload import parse_payload
from rewind.config import Config
from rewind.rollback import plan_rollback, restore
from rewind.sessions import SessionManager
from rewind.store.db import open_event_store


def _payload(kind: str, **extra: object) -> str:
    base: dict[str, object] = {
        "session_id": "full-1",
        "transcript_path": "/tmp/t.jsonl",
        "cwd": "/tmp",
        "permission_mode": "default",
        "hook_event_name": kind,
    }
    base.update(extra)
    return json.dumps(base)


def test_full_session_capture_and_rollback(rewind_home: Path, tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    target = project / "main.py"
    target.write_text("def hello():\n    return 1\n", encoding="utf-8")

    config = Config.from_env()
    config.ensure_dirs()
    manager = SessionManager(config)

    ingest_payload(
        payload=parse_payload(
            _payload("SessionStart", cwd=str(project), source="startup", model="opus")
        ),
        config=config,
        manager=manager,
        now_ms=100,
    )
    ingest_payload(
        payload=parse_payload(
            _payload("UserPromptSubmit", cwd=str(project), prompt="rename to greet")
        ),
        config=config,
        manager=manager,
        now_ms=110,
    )
    ingest_payload(
        payload=parse_payload(
            _payload(
                "PreToolUse",
                cwd=str(project),
                tool_name="Edit",
                tool_input={"file_path": str(target)},
                tool_use_id="t1",
            )
        ),
        config=config,
        manager=manager,
        now_ms=120,
    )
    target.write_text("def greet():\n    return 1\n", encoding="utf-8")
    ingest_payload(
        payload=parse_payload(
            _payload(
                "PostToolUse",
                cwd=str(project),
                tool_name="Edit",
                tool_input={"file_path": str(target)},
                tool_response={"success": True},
                duration_ms=8,
            )
        ),
        config=config,
        manager=manager,
        now_ms=130,
    )
    ingest_payload(
        payload=parse_payload(
            _payload(
                "Stop",
                cwd=str(project),
                exit_reason="normal",
                total_cost_usd=0.01,
                total_events=4,
            )
        ),
        config=config,
        manager=manager,
        now_ms=140,
    )

    paths = manager.session_paths("full-1")
    with open_event_store(paths.db) as store:
        events = store.list_events("full-1")
        assert [e.kind.value for e in events] == [
            "session_start",
            "user_prompt",
            "pre_tool",
            "post_tool",
            "session_end",
        ]
        plan = plan_rollback(store=store, session_id="full-1", target_seq=4, cwd=project)
    assert plan.restored == 1

    outcome = restore(plan=plan, config=config, cwd=project, force=False)
    assert outcome.plan.restored == 1
    assert target.read_text(encoding="utf-8") == "def hello():\n    return 1\n"
