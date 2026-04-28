# Architecture

> Technical design for `rewind`. Single-process Python CLI/TUI with local SQLite storage and content-addressed file snapshots.

---

## High-level flow

```
Claude Code
   │
   ├── SessionStart hook   ──┐
   ├── UserPromptSubmit hook ─┤
   ├── PreToolUse hook       ─┼──>  rewind capture <kind>  ──>  ~/.rewind/sessions/<id>/events.db
   ├── PostToolUse hook      ─┤                                    │
   └── Stop hook             ─┘                                    │
                                                                   ▼
                                                            ~/.rewind/sessions/<id>/blobs/
                                                            (content-addressed file snapshots)

Then:
   rewind tui <session_id>      → Rich TUI: timeline, diffs, scrub
   rewind goto <event_id>       → Rollback files
   rewind export --gif          → Render session to GIF/MP4
```

## Storage layout on disk

```
~/.rewind/
├── config.toml                  # global config (privacy, retention, defaults)
├── current_session.txt          # active session id (single line)
└── sessions/
    └── 2026-04-28-7f3a/
        ├── events.db            # SQLite, all events
        ├── meta.json            # session-level metadata (denormalized for quick listing)
        └── blobs/
            └── ab/cd/<sha256>   # file content snapshots, deduped
```

- Each session is fully self-contained. Easy to delete, share, export.
- Blobs are content-addressed: `sha256(content)[0:2]/sha256(content)[2:4]/sha256(content)`. Same file across snapshots = same blob.
- SQLite uses WAL mode for safe concurrent writes from multiple hook invocations.

## SQLite schema

```sql
-- One row per session
CREATE TABLE sessions (
    id              TEXT PRIMARY KEY,        -- e.g. '2026-04-28-7f3a'
    started_at      INTEGER NOT NULL,        -- unix epoch ms
    ended_at        INTEGER,                 -- null until session ends
    cwd             TEXT NOT NULL,           -- working dir at session start
    model           TEXT,                    -- last detected model
    total_cost_usd  REAL DEFAULT 0,
    total_tokens_in INTEGER DEFAULT 0,
    total_tokens_out INTEGER DEFAULT 0,
    total_events    INTEGER DEFAULT 0,
    exit_reason     TEXT                     -- 'normal' | 'aborted' | 'error'
);

-- One row per event in chronological order
CREATE TABLE events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    seq             INTEGER NOT NULL,        -- 1-based ordinal within session
    ts              INTEGER NOT NULL,        -- unix epoch ms
    kind            TEXT NOT NULL,           -- see EventKind enum
    tool_name       TEXT,                    -- 'Edit', 'Bash', 'Read', ...
    tool_input_json TEXT,                    -- raw input
    tool_output_json TEXT,                   -- raw output (truncated > 64KB)
    tool_status     TEXT,                    -- 'productive' | 'wasted' | 'neutral'
    cost_usd        REAL DEFAULT 0,
    tokens_in       INTEGER DEFAULT 0,
    tokens_out      INTEGER DEFAULT 0,
    duration_ms     INTEGER,
    model           TEXT
);

-- Files modified by this event. Each Edit/Write/MultiEdit/NotebookEdit emits
-- snapshot rows. before_hash captures the file content immediately before
-- this event ran; after_hash captures it after.
CREATE TABLE file_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        INTEGER NOT NULL REFERENCES events(id),
    path            TEXT NOT NULL,           -- absolute path
    before_hash     TEXT,                    -- sha256 of bytes before, or null if file did not exist
    after_hash      TEXT,                    -- sha256 of bytes after, or null if file deleted
    bytes_before    INTEGER,
    bytes_after     INTEGER
);

CREATE INDEX idx_events_session_seq ON events(session_id, seq);
CREATE INDEX idx_snapshots_event ON file_snapshots(event_id);
CREATE INDEX idx_snapshots_path ON file_snapshots(path);
```

### EventKind enum (string column)

| kind              | trigger                              | tool_input_json fields            |
|-------------------|--------------------------------------|------------------------------------|
| `session_start`   | SessionStart hook                    | model, cwd, env_summary           |
| `user_prompt`     | UserPromptSubmit hook                | prompt_text                       |
| `pre_tool`        | PreToolUse hook                      | tool_name, tool_input             |
| `post_tool`       | PostToolUse hook                     | tool_name, tool_input, tool_output, duration |
| `session_end`     | Stop hook                            | exit_reason, total_cost, totals   |

## Module layout (Python package)

```
src/rewind/
├── __init__.py
├── __main__.py
├── cli.py              # Click entry point
├── capture/
│   ├── __init__.py
│   ├── hooks.py        # Hook handlers (one fn per kind)
│   ├── stdin.py        # Parse Claude Code stdin payloads
│   └── snapshot.py     # File before/after capture, blob store writes
├── store/
│   ├── __init__.py
│   ├── db.py           # SQLite open, migrate, WAL
│   ├── blob.py         # Content-addressed blob storage
│   ├── models.py       # Dataclasses for Session, Event, FileSnapshot
│   └── queries.py      # All SELECTs, never inline SQL elsewhere
├── tui/
│   ├── __init__.py
│   ├── app.py          # Rich Live + Layout
│   ├── timeline.py     # Left pane: scrollable event list
│   ├── detail.py       # Right pane: event detail + diff
│   ├── diff.py         # Diff renderer (unified)
│   └── keys.py         # Keybinding handlers
├── rollback/
│   ├── __init__.py
│   ├── engine.py       # Goto event, write files from blobs, save undo checkpoint
│   └── safety.py       # Pre-rollback safety checks (uncommitted git, etc.)
├── export/
│   ├── __init__.py
│   ├── frames.py       # Build a list of frame specs from events
│   ├── render.py       # Render frames via PIL → GIF or imageio → MP4
│   └── overlay.py      # Cost / model / time overlays per frame
├── analytics/
│   ├── __init__.py
│   └── insights.py     # Cost breakdown, tool usage, "best/worst session"
├── config.py           # Load ~/.rewind/config.toml with sensible defaults
└── version.py
```

```
tests/
├── unit/
│   ├── test_capture.py
│   ├── test_store.py
│   ├── test_rollback.py
│   ├── test_export.py
│   └── test_analytics.py
└── integration/
    ├── test_hook_to_db.py       # full pipeline: stdin → events.db
    ├── test_rollback_real_fs.py # snapshot → modify → rollback → verify
    └── test_export_smoke.py     # tiny session → tiny GIF
```

## Hook integration with Claude Code

`rewind cc setup` modifies the user's Claude Code `settings.json` to register five hook commands. Each hook is a thin shell-out to `rewind capture <kind>` with stdin piped from Claude Code:

```json
{
  "hooks": {
    "SessionStart":      [{ "command": "rewind capture session-start" }],
    "UserPromptSubmit":  [{ "command": "rewind capture user-prompt" }],
    "PreToolUse":        [{ "command": "rewind capture pre-tool" }],
    "PostToolUse":       [{ "command": "rewind capture post-tool" }],
    "Stop":              [{ "command": "rewind capture session-end" }]
  }
}
```

Hook handler responsibilities:
- Parse JSON stdin payload from Claude Code.
- Append to `events.db` in the active session.
- For `pre_tool` on Edit/Write/MultiEdit/NotebookEdit: capture the *before* file content as a blob and record `before_hash`.
- For `post_tool` on the same tools: capture the *after* file content and record `after_hash`.
- Never block; if write fails, log to stderr and exit 0 (do not crash the parent agent).
- Target latency: < 50ms per hook. SQLite WAL writes are ~1-5ms typically.

## Rollback semantics

`rewind goto <event_seq>` restores the file system to the state *just before* event `event_seq` ran.

Algorithm:
1. Fetch all `file_snapshots` rows for events with `seq < event_seq`.
2. For each unique `path`, find the most recent `after_hash` (or `before_hash` of the first snapshot if no prior `after_hash`).
3. Save current files at those paths to a *checkpoint snapshot* (so the rollback itself is reversible).
4. Write each file from its blob (or delete the file if blob is null).
5. Print summary: N files restored, N deleted, M unchanged.

Safety checks:
- Refuse to rollback if working directory has uncommitted git changes (override with `--force`).
- Refuse to rollback paths outside `cwd` (override with `--force`).
- Always create a checkpoint before rolling back, so `rewind undo` reverses it.

## Export to GIF/MP4

`rewind export <session_id> --format gif --speed 60x --out session.gif`

Each event becomes one or more frames. Frame specs are computed from the event stream (no live capture needed):

| Event kind     | Frames | Visual                                                  |
|----------------|--------|---------------------------------------------------------|
| session_start  | 1      | Title card: model, cwd, start time                      |
| user_prompt    | 2      | Prompt text appears, brief pause                        |
| pre_tool       | 1      | Tool name + first 80 chars of input slide in            |
| post_tool      | 2-4    | Output preview + cost overlay; for Edit: mini diff      |
| session_end    | 2      | Summary card: total cost, tokens, files changed, time   |

Render path: PIL composes each frame as RGB at 1280x720, imageio assembles to GIF or MP4. Default GIF for portability, MP4 for sharing on platforms that prefer video.

Privacy: by default the export *masks* file contents to first/last 8 lines and redacts environment variable values. `--no-mask` disables masking explicitly.

## Performance budget

| Operation            | Target latency | Notes |
|----------------------|----------------|-------|
| Hook write (per event) | < 50 ms      | SQLite WAL + blob store |
| Blob write (per file) | < 20 ms       | Content-addressed, dedup |
| Open TUI for a session of 200 events | < 1 s | Indexed query |
| Render 60s GIF       | < 30 s         | PIL is the bottleneck |
| Rollback 50-file change | < 1 s        | Bulk blob reads |

## Privacy & safety defaults

- Local-only storage. Zero network calls in V1.
- No telemetry, anonymous or otherwise.
- Default `.gitignore` template: `.rewind/`.
- Recommend disabling rewind on repos with secrets (TUI shows a warning if env vars look sensitive).
- Export: file contents masked by default. Explicit opt-out required.
- Retention: default keep last 30 sessions, configurable. Old sessions auto-pruned.

## Edge cases

- **Files > 10 MB:** store SHA + size only (no full blob). Diff is degraded but rollback still works for textual subsets.
- **Binary files:** SHA + size only.
- **Symlinks:** follow with depth limit 8.
- **Permission errors:** log and skip; never abort hook.
- **Very large output (> 64 KB):** truncate `tool_output_json`, store full output as a blob if essential.
- **Concurrent sessions:** distinguished by Claude Code session id; each gets its own dir.
- **Hook command not on PATH:** `rewind cc setup` writes the absolute path to settings.json by default.

## Future (V2+) — explicitly NOT in V1

- Live tail TUI (separate terminal, watches events as they arrive).
- Web dashboard (Next.js) for shareable URLs of sessions.
- Encrypted storage at rest with user passphrase.
- Cloud sync / team mode.
- Editor plugins.
- Cross-tool support (Cursor, Aider, Codex)— V1 is Claude Code only.
- AI summary: "what did this session accomplish" via local LLM call.
- Diff against a baseline session (compare two sessions side-by-side).
