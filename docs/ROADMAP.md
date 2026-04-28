# Roadmap

> 6 phases, ~1 calendar week each. Sin prisa. Don't ship a phase until it earns it.

---

## Phase 0 — Pre-work (this week)

Decisions and pre-flight items. Cannot start Phase 1 until done.

- [ ] Verify name availability:
  - PyPI: `pip search` is dead, check via `https://pypi.org/project/rewind/`
  - GitHub: check `github.com/<user>/rewind`
  - npm (just to be safe): `npmjs.com/package/rewind`
  - Domain: check `rewind.dev`, `rewind.tools`, `getrewind.dev`
  - If `rewind` is not available, fall back to `chrono` then `unwind` (see [NAMING.md](NAMING.md))
- [ ] Reserve PyPI name (publish a stub `0.0.1` if needed)
- [ ] Create the repo: `github.com/loplop-h/rewind`
- [ ] Buy domain
- [ ] Set up uv / pyproject.toml skeleton
- [ ] Decide build-in-public schedule: 1 LinkedIn post per phase (6 total)

**Exit criteria:** name locked, repo created, domain purchased, pyproject.toml committed.

---

## Phase 1 — Foundations & schema (week 1)

Get the boring infrastructure right so the fun stuff is easy.

### Tasks
- [ ] Pyproject.toml: deps (click, rich, pillow, imageio), entry points, py3.11+
- [ ] CLI scaffold: `rewind --help`, `rewind version`, `rewind cc setup`, `rewind cc status`
- [ ] SQLite schema (see ARCHITECTURE.md), migrations directory
- [ ] Models: `Session`, `Event`, `FileSnapshot` dataclasses
- [ ] Blob store: read/write content-addressed blobs
- [ ] Config loader: `~/.rewind/config.toml` with sensible defaults
- [ ] Logger: structured stderr logging, `--verbose` flag
- [ ] CI: GitHub Actions for pytest + ruff + type check
- [ ] Test coverage gate: 80% min on store/ and config/

### Out
- No TUI yet
- No hooks running
- No export

### Build-in-public post #1 (end of phase)
"Started building `rewind` — a time-travel debugger for Claude Code sessions. Today's milestone: the schema. Here's how I'm storing every tool call, file snapshot, and cost in a single SQLite file. [screenshot of schema]. Next up: capturing real sessions."

---

## Phase 2 — Capture pipeline (week 2)

Wire up Claude Code hooks. End of week: real sessions stored end-to-end.

### Tasks
- [ ] `rewind capture <kind>` subcommand reading stdin JSON
- [ ] One handler per kind: session_start, user_prompt, pre_tool, post_tool, session_end
- [ ] File snapshot logic for Edit / Write / MultiEdit / NotebookEdit
  - Read current bytes → write to blob → record before_hash
  - On post_tool: read again → record after_hash
- [ ] `rewind cc setup` modifies user's Claude Code `settings.json` (with backup)
- [ ] `rewind cc uninstall` reverses the above
- [ ] `rewind sessions list` — show all captured sessions with cost summary
- [ ] Integration test: simulated full Claude Code session → events.db has 50+ rows

### Self-test
Run rewind against your own daily Claude Code use for 3+ days. Bug-fix until rock solid.

### Build-in-public post #2 (end of phase)
"Just hit a milestone with `rewind` — it now captures every event from a Claude Code session. Below: yesterday's session — 47 tool calls, $1.23, 6 files changed. Each one stored, indexed, ready to scrub. Tomorrow: the timeline UI."

---

## Phase 3 — TUI timeline + diff viewer (week 3)

The "wow" demo. Spend extra polish time here.

### Tasks
- [ ] `rewind tui [<session_id>]` — defaults to most recent session
- [ ] Layout: left pane (timeline list), right pane (detail), top status bar
- [ ] Timeline rendering:
  - Color-coded by tool kind (Edit=cyan, Bash=yellow, Read=dim, Errors=red)
  - Show: time, tool, status icon, brief summary, cost
- [ ] Keybindings: ↑↓, →/Enter, ←/Esc, /, q, r (rollback), e (export from here)
- [ ] Detail pane:
  - Tool input (formatted)
  - Tool output (truncated with "press d for full diff")
  - For Edit/Write: side-by-side or unified diff
- [ ] Search: `/` opens query box, fuzzy match on tool input/output
- [ ] Smooth navigation (no flicker, no lag with 1000+ event sessions)

### Out
- No rollback yet (just stub the `r` key with a placeholder)
- No export yet

### Build-in-public post #3 (end of phase)
"`rewind`: now I can scrub through a 4-hour Claude Code session like a video. Found a bug from earlier today — file got rewritten, output looked fine, but the agent had skipped a function. Fix took 30 seconds because I could see the exact tool call. [GIF of TUI scrub]. Tomorrow: rollback."

---

## Phase 4 — Rollback engine (week 4)

The killer feature: undo any AI mistake.

### Tasks
- [ ] `rewind goto <event_seq>` — restore file system to state before that event
- [ ] Pre-rollback checkpoint (so `rewind undo` reverses)
- [ ] Safety: refuse if uncommitted git changes; `--force` to override
- [ ] Safety: refuse paths outside cwd; `--force` to override
- [ ] `rewind undo` — reverse the last rollback
- [ ] `r` key in TUI triggers rollback prompt with confirmation
- [ ] Print summary: N files restored, N deleted, M unchanged
- [ ] Tests: real filesystem, with edge cases (deleted files, binary files, large files)

### Self-test
Use rollback in real life at least 5 times during the week. Fix anything that feels rough.

### Build-in-public post #4 (end of phase)
"Demo of `rewind goto` in action: agent broke 4 files at 14:32. One command at 14:47 — `rewind goto 31` — and we're back. Then the AI got it right second try. [GIF: 30 seconds, before/after states]."

---

## Phase 5 — Analytics + export (week 5)

Insights overlay + the viral feature.

### Tasks
- [ ] `rewind stats` CLI — text dashboard:
  - Total cost / tokens / events / sessions
  - Per-model breakdown
  - Top 10 tool calls by cost
  - Wasted vs productive %
- [ ] Insights pane in TUI (toggleable with `i`)
- [ ] `rewind export <session> --format gif|mp4 --out <file>`
  - Frame builder from event stream
  - PIL for static frames, imageio for assembly
  - Privacy: mask file contents by default (`--no-mask` to disable)
  - Watermark "made with rewind" (default on, `--no-watermark` to disable)
  - Speed control: `--speed 30x|60x|120x` (default 60x)
- [ ] Aim for 30-90 second output for a typical 1-hour session

### Build-in-public post #5 (end of phase)
"`rewind export --gif` is live. This 60-second clip is my actual Claude Code session from this morning — 32 tool calls, $0.84, 11 files changed. Compressed to a minute. Now imagine this on every PR description. [the GIF itself]."

---

## Phase 6 — Polish, README, launch (week 6)

The most important phase. Skip nothing.

### Tasks
- [ ] README rewrite to viral-grade:
  - Hero GIF in first 3 seconds
  - One-paragraph pitch
  - 5-line install
  - Key commands table
  - 3-section "what / why / how"
  - Roadmap, license, contributing
- [ ] Landing page on Vercel (rewind.dev or fallback)
- [ ] Polish all CLI output: errors, help text, examples
- [ ] Verify: install on Mac, Linux, Windows
- [ ] Pre-launch beta with 30-50 people from spent's audience:
  - DM each personally (not pitch — invite to test)
  - Collect feedback
  - Ask for upvotes on launch day in advance
- [ ] LICENSE file (MIT)
- [ ] CONTRIBUTING.md
- [ ] Tag v0.1.0 on PyPI
- [ ] Pre-write all launch posts: HN, Reddit (4 subs), Twitter, LinkedIn, ProductHunt
- [ ] Schedule launch for Tuesday or Wednesday morning Barcelona time

### Build-in-public post #6 (the launch)
See [LAUNCH.md](LAUNCH.md).

---

## After launch (week 7+)

### First 24 hours
- Respond to every comment within 1 hour
- Critical bugs: hot-fix and ship same day
- Move featured posts on profile to highlight rewind

### First week
- Daily updates on usage stats and stars
- Submit to awesome lists: awesome-claude-code, awesome-mcp, awesome-cli
- Pitch to AI / dev tool newsletters

### First month
- V0.2 features based on feedback
- Maybe: Cursor / Aider integration if demand exists
- Maybe: web dashboard if many users want shareable URLs

---

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Anthropic ships native session viewer | Medium | High | Differentiate via export GIF + cross-tool potential |
| Performance issues on big sessions | Medium | Medium | Test with 1000+ event sessions during dev |
| LinkedIn audience tired of dev tools | Low | Medium | New angle: "share your session" as the hook |
| Name conflict at last minute | Low | High | Phase 0 verifies before any code |
| Privacy concern blowback | Medium | High | Default-mask exports, clear opt-in language |
| Hook integration brittle across CC versions | Medium | Medium | Pin to current API, document supported versions |
