# Changelog

All notable changes to **rewind** are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
