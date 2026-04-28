"""Click-based command-line interface for rewind."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any

import click

from rewind.analytics import compute_insights
from rewind.capture.hooks import ingest_payload
from rewind.capture.payload import parse_payload
from rewind.cc_setup import (
    SETUP_HOOK_NAMES,
    install_claude_code_hooks,
    locate_claude_code_settings,
    show_status,
    uninstall_claude_code_hooks,
)
from rewind.config import Config
from rewind.export.frames import build_frames, render_markdown, render_text
from rewind.rollback import (
    plan_rollback,
    restore,
    safety_errors_from,
    undo_last,
)
from rewind.sessions import SessionManager
from rewind.store.db import open_event_store
from rewind.tui.app import run_tui
from rewind.version import __version__


@click.group(invoke_without_command=False, context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="rewind")
@click.pass_context
def main(ctx: click.Context) -> None:
    """rewind — time-travel debugger for Claude Code sessions."""

    ctx.ensure_object(dict)
    ctx.obj["config"] = Config.load()


@main.group(name="cc")
def cc_group() -> None:
    """Manage Claude Code hook integration."""


@cc_group.command("setup")
@click.option("--scope", type=click.Choice(["user", "project"]), default="user", show_default=True)
@click.option("--project-dir", type=click.Path(file_okay=False, path_type=Path))
@click.pass_context
def cc_setup(ctx: click.Context, scope: str, project_dir: Path | None) -> None:
    """Install rewind hooks into Claude Code's settings.json."""

    config = _config(ctx)
    settings_path = locate_claude_code_settings(scope=scope, project_dir=project_dir)
    install_claude_code_hooks(
        settings_path=settings_path,
        rewind_command=_self_command(),
        config=config,
    )
    click.echo(f"installed rewind hooks into {settings_path}")
    click.echo("hooks: " + ", ".join(SETUP_HOOK_NAMES))


@cc_group.command("uninstall")
@click.option("--scope", type=click.Choice(["user", "project"]), default="user", show_default=True)
@click.option("--project-dir", type=click.Path(file_okay=False, path_type=Path))
@click.pass_context
def cc_uninstall(ctx: click.Context, scope: str, project_dir: Path | None) -> None:
    """Remove rewind hooks from Claude Code's settings.json."""

    _ = ctx
    settings_path = locate_claude_code_settings(scope=scope, project_dir=project_dir)
    removed = uninstall_claude_code_hooks(settings_path=settings_path)
    if removed:
        click.echo(f"removed rewind hooks from {settings_path}")
    else:
        click.echo("no rewind hooks were configured")


@cc_group.command("status")
@click.option("--scope", type=click.Choice(["user", "project"]), default="user", show_default=True)
@click.option("--project-dir", type=click.Path(file_okay=False, path_type=Path))
@click.pass_context
def cc_status(ctx: click.Context, scope: str, project_dir: Path | None) -> None:
    """Show whether rewind hooks are configured."""

    _ = ctx
    settings_path = locate_claude_code_settings(scope=scope, project_dir=project_dir)
    status = show_status(settings_path)
    click.echo(status)


@main.command("capture")
@click.argument(
    "kind",
    type=click.Choice(
        [
            "session-start",
            "user-prompt",
            "pre-tool",
            "post-tool",
            "session-end",
        ]
    ),
)
@click.pass_context
def capture(ctx: click.Context, kind: str) -> None:
    """Read a hook payload from stdin and append it to the active session."""

    _ = kind
    config = _config(ctx)
    raw = sys.stdin.read()
    if not raw.strip():
        return
    try:
        payload = parse_payload(raw)
    except ValueError as exc:
        click.echo(f"rewind: {exc}", err=True)
        return
    manager = SessionManager(config)
    try:
        ingest_payload(payload=payload, config=config, manager=manager)
    except Exception as exc:  # pragma: no cover - last resort
        click.echo(f"rewind: capture failed: {exc}", err=True)


@main.group(name="sessions")
def sessions_group() -> None:
    """Inspect captured sessions."""


@sessions_group.command("list")
@click.pass_context
def sessions_list(ctx: click.Context) -> None:
    """List captured sessions, newest first."""

    config = _config(ctx)
    manager = SessionManager(config)
    sessions = manager.list_sessions()
    if not sessions:
        click.echo("no sessions captured yet")
        return
    click.echo(f"{'session':<40}  {'started':<20}  events  cost")
    for s in sessions:
        click.echo(
            f"{s.id[:36]:<40}  {_iso(s.started_at):<20}  "
            f"{s.total_events:>6}  ${s.total_cost_usd:.2f}"
        )


@sessions_group.command("show")
@click.argument("session_id")
@click.pass_context
def sessions_show(ctx: click.Context, session_id: str) -> None:
    """Print the timeline of a session."""

    config = _config(ctx)
    rc = run_tui(config=config, session_id=session_id)
    sys.exit(rc)


@sessions_group.command("delete")
@click.argument("session_id")
@click.option("--force", is_flag=True, help="Skip confirmation")
@click.pass_context
def sessions_delete(ctx: click.Context, session_id: str, force: bool) -> None:
    """Delete a captured session and all its blobs."""

    config = _config(ctx)
    if not force and not click.confirm(f"delete session {session_id} and all blobs?"):
        click.echo("aborted")
        return
    manager = SessionManager(config)
    if manager.delete_session(session_id):
        click.echo(f"deleted {session_id}")
    else:
        click.echo(f"session not found: {session_id}", err=True)
        sys.exit(2)


@main.command("tui")
@click.argument("session_id", required=False)
@click.option("--seq", type=int, default=None, help="Show full detail for this event seq")
@click.pass_context
def tui_command(ctx: click.Context, session_id: str | None, seq: int | None) -> None:
    """Open a non-interactive timeline view for the latest (or named) session."""

    config = _config(ctx)
    rc = run_tui(config=config, session_id=session_id, seq=seq)
    sys.exit(rc)


@main.command("goto")
@click.argument("seq", type=int)
@click.option("--session", "session_id", default=None, help="Session id (default: latest)")
@click.option("--cwd", "cwd_arg", type=click.Path(file_okay=False, path_type=Path), default=None)
@click.option("--force", is_flag=True, help="Skip uncommitted-changes / cwd-containment checks")
@click.option("--dry-run", is_flag=True, help="Plan only; do not write to disk")
@click.pass_context
def goto(
    ctx: click.Context,
    seq: int,
    session_id: str | None,
    cwd_arg: Path | None,
    force: bool,
    dry_run: bool,
) -> None:
    """Roll back the file system to just before event #SEQ."""

    config = _config(ctx)
    manager = SessionManager(config)
    session = _resolve_session(manager, session_id)
    cwd = (cwd_arg or Path(session.cwd)).resolve()
    paths = manager.session_paths(session.id)
    with open_event_store(paths.db) as store:
        plan = plan_rollback(store=store, session_id=session.id, target_seq=seq, cwd=cwd)
    click.echo(
        f"plan: {plan.restored} restore, {plan.deleted} delete, {plan.unchanged} unchanged "
        f"(target seq={seq})"
    )
    for change in plan.changes:
        click.echo(f"  {change.action.value:<9} {change.path}")
    if dry_run:
        return
    if not force:
        errs = list(safety_errors_from(plan, cwd))
        if errs:
            for err in errs:
                click.echo(f"rewind: {err}", err=True)
            click.echo("hint: pass --force to override", err=True)
            sys.exit(2)
    outcome = restore(plan=plan, config=config, cwd=cwd, force=force)
    click.echo(f"rolled back. checkpoint id: {outcome.checkpoint_id}")


@main.command("undo")
@click.pass_context
def undo(ctx: click.Context) -> None:
    """Reverse the most recent rollback."""

    config = _config(ctx)
    outcome = undo_last(config=config)
    if outcome is None:
        click.echo("nothing to undo")
        sys.exit(1)
    click.echo(
        f"undone checkpoint {outcome.checkpoint_id}: "
        f"{outcome.plan.restored} restored, {outcome.plan.deleted} deleted"
    )


@main.command("stats")
@click.argument("session_id", required=False)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of human-readable")
@click.pass_context
def stats(ctx: click.Context, session_id: str | None, as_json: bool) -> None:
    """Compute insights for a session (or the latest one)."""

    config = _config(ctx)
    manager = SessionManager(config)
    session = _resolve_session(manager, session_id)
    paths = manager.session_paths(session.id)
    with open_event_store(paths.db) as store:
        insights = compute_insights(store, session.id)
    if insights is None:
        click.echo(f"session not found: {session.id}", err=True)
        sys.exit(2)
    if as_json:
        click.echo(json.dumps(_insights_to_dict(insights), indent=2))
        return
    click.echo(f"session  {session.id}")
    click.echo(
        f"events   {insights.event_count} ({insights.user_prompt_count} prompts, "
        f"{insights.post_tool_count} tool calls)"
    )
    click.echo(
        f"status   {insights.productive_pct:.0f}% productive · {insights.waste_pct:.0f}% wasted"
    )
    click.echo(f"files    {insights.files_touched} touched")
    if insights.tool_breakdown:
        click.echo("\ntop tools:")
        for tool in insights.tool_breakdown[:10]:
            click.echo(
                f"  {tool.tool_name:<20}  {tool.calls:>4} calls  ({tool.waste_pct:.0f}% wasted)"
            )


@main.command("export")
@click.argument("session_id", required=False)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "markdown"]),
    default="markdown",
    show_default=True,
)
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--no-mask", is_flag=True, help="Do not mask file contents (PRIVACY: dangerous)")
@click.pass_context
def export_command(
    ctx: click.Context,
    session_id: str | None,
    fmt: str,
    out: Path | None,
    no_mask: bool,
) -> None:
    """Render a session as a shareable transcript (text or markdown)."""

    config = _config(ctx)
    manager = SessionManager(config)
    session = _resolve_session(manager, session_id)
    paths = manager.session_paths(session.id)
    with open_event_store(paths.db) as store:
        events = store.list_events(session.id)
    frames = build_frames(session=session, events=events, mask=not no_mask)
    rendered = render_text(frames) if fmt == "text" else render_markdown(frames, session=session)
    _emit(rendered, out=out)


def _emit(content: str, *, out: Path | None) -> None:
    if out is None:
        sys.stdout.write(content)
        return
    out.write_text(content, encoding="utf-8")
    click.echo(f"wrote {out}")


def _config(ctx: click.Context) -> Config:
    config = ctx.obj.get("config") if ctx.obj else None
    return config if isinstance(config, Config) else Config.load()


def _resolve_session(manager: SessionManager, session_id: str | None) -> Any:
    if session_id is not None:
        if not manager.has_session(session_id):
            raise click.ClickException(f"session not found: {session_id}")
        sessions = manager.list_sessions()
        for s in sessions:
            if s.id == session_id:
                return s
        raise click.ClickException(f"session not found: {session_id}")
    latest = manager.latest_session()
    if latest is None:
        raise click.ClickException("no sessions captured yet")
    return latest


def _self_command() -> str:
    """Return the command we want hooks to invoke (resolved python -m for portability)."""

    return f"{sys.executable} -m rewind capture"


def _iso(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M")


def _insights_to_dict(insights: Any) -> dict[str, Any]:
    return {
        "session_id": insights.session.id,
        "event_count": insights.event_count,
        "productive_pct": insights.productive_pct,
        "waste_pct": insights.waste_pct,
        "files_touched": insights.files_touched,
        "tools": [
            {
                "name": t.tool_name,
                "calls": t.calls,
                "productive": t.productive,
                "wasted": t.wasted,
                "neutral": t.neutral,
                "waste_pct": t.waste_pct,
            }
            for t in insights.tool_breakdown
        ],
    }


def _drain_stdin(stream: IO[str]) -> str:
    return stream.read()


if __name__ == "__main__":  # pragma: no cover
    main()
