# Changelog

All notable changes to **rewind** are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Fixed

### Removed

## [0.1.3] — 2026-04-28

### Fixed
- **Critical (Windows + Claude Code real sessions):** the hook commands
  written by ``rewind cc setup`` used ``sys.executable`` directly, which
  on Windows is a path with backslashes such as
  ``C:\\Users\\…\\python.exe``. Claude Code runs those hooks through
  ``/usr/bin/bash`` (Git Bash / MSYS) even on Windows, and bash treats
  ``\\`` as an escape character — so the path collapsed to
  ``C:Users…python.exe`` and **every single hook fired by Claude Code on
  Windows failed with ``command not found``**. The console-tested
  ``rewind cc setup`` worked because tests don't invoke Claude Code, so
  CI never saw it.

  Fix: ``_self_command()`` now emits the executable path in POSIX form
  (forward slashes) inside single quotes, which suppresses all shell
  expansion. Verified end-to-end against a real Claude Code session.

  **Action required:** Windows users who installed 0.1.0 or 0.1.2 must
  re-run ``rewind cc setup`` (any scope) once after upgrading to 0.1.3
  so the now-broken hook commands in their settings.json are
  regenerated.

## [0.1.2] — 2026-04-28

### Fixed
- **Critical (Windows):** `rewind tui` crashed with ``UnicodeEncodeError``
  on the default Windows cp1252 console because the Rich box-drawing
  characters in the timeline could not be encoded. The CLI now forces
  ``sys.stdout`` / ``sys.stderr`` to UTF-8 with ``errors="replace"`` on
  startup, so any output renders cleanly regardless of the system locale.

### Skipped
- 0.1.1 was released only as a marketing-asset bump (hero PNG, rollback
  GIF, launch copy) with no functional changes; the wheel was not
  republished. 0.1.2 is the first release that updates the package
  contents after 0.1.0.

## [0.1.0] — 2026-04-28

Initial alpha. Core capture + rollback + export pipeline. Non-interactive TUI.

### Added
- `rewind cc {setup,uninstall,status}` to manage Claude Code hooks in
  `~/.claude/settings.json` (user scope) or `<project>/.claude/settings.json`
  (project scope) with idempotent install and one-time `.rewind-backup`.
- `rewind capture <kind>` reads a hook payload from stdin and persists it
  as one event (and file snapshots when applicable).
- Per-session SQLite event store at `~/.rewind/sessions/<id>/events.db` with
  WAL mode, content-addressed blob storage at `<id>/blobs/<aa>/<bb>/<sha256>`,
  and a single migration target (schema v1).
- Tool classification (productive / neutral / wasted) compatible with `spent`'s
  taxonomy.
- `rewind sessions {list,show,delete}` for inspection and cleanup.
- `rewind tui [SESSION_ID] [--seq N]` non-interactive timeline view.
- `rewind goto SEQ [--session] [--cwd] [--force] [--dry-run]` rollback engine
  with safety checks (uncommitted changes, paths outside cwd) and pre-rollback
  checkpointing so `rewind undo` reverses.
- `rewind stats [SESSION_ID] [--json]` per-session insights.
- `rewind export [SESSION_ID] [--format text|markdown] [--out PATH] [--no-mask]`
  shareable transcripts with default privacy masking.
- Configuration via `~/.rewind/config.toml` (`retention_sessions`,
  `max_blob_bytes`, `tool_output_truncate_bytes`, `capture_disabled`); unknown
  keys preserved in `extra` for forward compatibility.
- 131 tests, 87% branch coverage, mypy strict, ruff lint and format clean.

### Notes
- The package name on PyPI is `rewindx`; the CLI command and brand are
  `rewind`. The bare PyPI name `rewind` was unavailable.
- Privacy is local-first by default: zero network calls, no telemetry. Exports
  mask file contents and env-shaped secrets unless `--no-mask` is passed.
- The interactive scrubbing TUI lands in 0.2.0 — current TUI is non-interactive
  but renders the same data.

[0.1.0]: https://github.com/loplop-h/rewind/releases/tag/v0.1.0
