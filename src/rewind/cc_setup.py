"""Install / uninstall rewind hooks into Claude Code's settings.json.

Claude Code looks for hook configuration in (in order):

* user scope:  ``~/.claude/settings.json``
* project scope:  ``<project>/.claude/settings.json``

We modify the ``hooks`` block in-place, leaving every other key untouched, and
keep a backup at ``settings.json.rewind-backup`` the first time we touch a
file. ``rewind cc uninstall`` removes only the entries we added (matched by
the rewind-prefixed command string).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rewind.config import Config

SETUP_HOOK_NAMES: tuple[str, ...] = (
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "Stop",
)

REWIND_MARKER = "rewind capture"


def locate_claude_code_settings(
    *,
    scope: str = "user",
    project_dir: Path | None = None,
) -> Path:
    """Return the path to the relevant ``settings.json`` for the chosen scope."""

    if scope == "project":
        if project_dir is None:
            project_dir = Path.cwd()
        return project_dir / ".claude" / "settings.json"
    if scope == "user":
        return Path.home() / ".claude" / "settings.json"
    raise ValueError(f"unknown scope: {scope!r}")


def install_claude_code_hooks(
    *,
    settings_path: Path,
    rewind_command: str,
    config: Config,
) -> None:
    """Idempotently install rewind hooks into ``settings_path``."""

    _ = config
    settings = _load_or_init(settings_path)
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError(f"unexpected hooks value in {settings_path}: {type(hooks).__name__}")
    for hook_name in SETUP_HOOK_NAMES:
        bucket = hooks.setdefault(hook_name, [])
        if not isinstance(bucket, list):
            raise ValueError(
                f"unexpected hooks.{hook_name} value in {settings_path}: {type(bucket).__name__}"
            )
        command = f"{rewind_command} {_kind_for(hook_name)}"
        if not _matcher_already_present(bucket, command):
            bucket.append(_matcher_block(hook_name=hook_name, command=command))
    _backup_once(settings_path)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


def uninstall_claude_code_hooks(*, settings_path: Path) -> bool:
    """Remove rewind-installed entries. Return True if anything was removed."""

    if not settings_path.exists():
        return False
    settings = _load_or_init(settings_path)
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return False
    changed = False
    for hook_name in SETUP_HOOK_NAMES:
        bucket = hooks.get(hook_name)
        if not isinstance(bucket, list):
            continue
        new_bucket = [m for m in bucket if not _is_rewind_matcher(m)]
        if len(new_bucket) != len(bucket):
            changed = True
            if new_bucket:
                hooks[hook_name] = new_bucket
            else:
                del hooks[hook_name]
    if changed:
        settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return changed


def show_status(settings_path: Path) -> str:
    """Return a one-line status describing the current install state."""

    if not settings_path.exists():
        return f"not installed (no file at {settings_path})"
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return f"settings file invalid JSON: {exc}"
    hooks = settings.get("hooks") or {}
    if not isinstance(hooks, dict):
        return f"settings.hooks not an object in {settings_path}"
    found = []
    for hook_name in SETUP_HOOK_NAMES:
        bucket = hooks.get(hook_name)
        if isinstance(bucket, list) and any(_is_rewind_matcher(m) for m in bucket):
            found.append(hook_name)
    if not found:
        return f"not installed (no rewind hooks in {settings_path})"
    return f"installed at {settings_path} ({len(found)}/5 hooks): {', '.join(found)}"


def _kind_for(hook_name: str) -> str:
    mapping = {
        "SessionStart": "session-start",
        "UserPromptSubmit": "user-prompt",
        "PreToolUse": "pre-tool",
        "PostToolUse": "post-tool",
        "Stop": "session-end",
    }
    return mapping[hook_name]


def _matcher_block(*, hook_name: str, command: str) -> dict[str, Any]:
    _ = hook_name  # we currently use the same matcher for every hook kind
    matcher = "*"
    return {
        "matcher": matcher,
        "hooks": [
            {
                "type": "command",
                "command": command,
                "timeout": 10,
            }
        ],
    }


def _matcher_already_present(bucket: list[Any], command: str) -> bool:
    for entry in bucket:
        if not isinstance(entry, dict):
            continue
        for hk in entry.get("hooks") or []:
            if isinstance(hk, dict) and hk.get("command") == command:
                return True
    return False


def _is_rewind_matcher(matcher: Any) -> bool:
    if not isinstance(matcher, dict):
        return False
    for hk in matcher.get("hooks") or []:
        if isinstance(hk, dict) and REWIND_MARKER in str(hk.get("command", "")):
            return True
    return False


def _load_or_init(settings_path: Path) -> dict[str, Any]:
    if not settings_path.exists():
        return {}
    text = settings_path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"settings.json at {settings_path} is invalid: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"settings.json at {settings_path} is not a JSON object")
    return loaded


def _backup_once(settings_path: Path) -> None:
    backup = settings_path.with_suffix(settings_path.suffix + ".rewind-backup")
    if backup.exists() or not settings_path.exists():
        return
    backup.write_bytes(settings_path.read_bytes())
