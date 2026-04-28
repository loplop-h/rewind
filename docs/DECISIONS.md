# Decisions Log

> Architectural Decision Records (ADR-style). One section per decision. New decisions appended at the bottom.

---

## ADR-001: Python over Rust / Go

**Date:** 2026-04-28
**Status:** Accepted

**Context.** Could build the capture+TUI+export pipeline in Python, Rust, or Go. Each has tradeoffs: Rust is faster and gets more credibility from "serious infra people" but takes longer; Go is fine but Max doesn't use it; Python is fast to ship and has the same toolchain as `spent`.

**Decision.** Python 3.11+.

**Rationale.**
- Same stack as `spent`. Zero curve.
- Hooks for Claude Code are shell-outs, so the language barely affects perf.
- SQLite + Rich + PIL covers everything in V1.
- We win on time-to-launch, not on micro-benchmarks.

**Consequences.** Slightly slower startup vs Rust, but startup happens once per hook (< 50 ms target is achievable). Distribution via pip is universal. Trade-off acceptable.

---

## ADR-002: SQLite single-file storage, not Postgres / lmdb / flat files

**Date:** 2026-04-28
**Status:** Accepted

**Context.** Need to store potentially thousands of events per session, with fast queries by time and event id, plus blob references.

**Decision.** SQLite per session, content-addressed blobs in directories.

**Rationale.**
- No daemon to install or run.
- Single-file portability: a session is one folder, easy to share / archive / delete.
- WAL mode handles concurrent hook writes from Claude Code.
- Indexed time-range queries are sub-millisecond at our scale.

**Consequences.** No remote/network storage in V1. If we ever need cloud sync, we add a separate sync layer; SQLite stays local.

---

## ADR-003: Local-only, no telemetry

**Date:** 2026-04-28
**Status:** Accepted

**Context.** Many dev tools ship with anonymous telemetry. It's controversial. We need user trust for a tool that captures every keystroke an AI agent makes.

**Decision.** Zero network calls in V1. No telemetry, anonymous or otherwise.

**Rationale.**
- Trust is the most valuable asset for a tool that observes everything.
- Default-on telemetry will be the first thing competitors weaponize against us.
- We can add opt-in cloud features in V2 with a clean conscience.
- Distinguishes us from a future Anthropic-built session viewer that might phone home.

**Consequences.** No usage data → harder to know what features people use. Mitigation: surveys, qualitative feedback, public stats users opt to share.

---

## ADR-004: Claude Code first, not multi-agent in V1

**Date:** 2026-04-28
**Status:** Accepted

**Context.** The same problem (no replay/rollback) exists in Cursor, Aider, Codex, etc. Tempting to build cross-tool from day one.

**Decision.** Claude Code only in V1. Other tools considered for V2.

**Rationale.**
- Each tool has its own hook/event model. Building all at once means none get done well.
- "Time-travel debugger for Claude Code" is a sharper LinkedIn / HN headline than a generic one.
- Max's audience is Claude Code-heavy. Lead where you have distribution.
- Once V1 is tight, porting a capture layer to Cursor's hooks or Aider's session log is a 1-2 week add.

**Consequences.** TAM is smaller in V1. Will pivot multi-tool in V2 if signal is strong.

---

## ADR-005: Content-addressed blob storage for file snapshots

**Date:** 2026-04-28
**Status:** Accepted

**Context.** Need to capture file content at every Edit/Write so rollback works. Naive approach: copy the file every time. Wasteful.

**Decision.** Hash content with SHA-256, store in `blobs/ab/cd/<hash>` directory tree. Reference blobs by hash in `file_snapshots` rows.

**Rationale.**
- Same content across snapshots = one blob. Massive dedup for slow-changing files.
- Cheap to verify integrity.
- Simple algorithm, no external lib needed.
- Same model as git's object store — well-understood pattern.

**Consequences.** Slight extra complexity in the snapshot writer. Worth it for the disk savings.

---

## ADR-006: Default-mask exports, opt-out only

**Date:** 2026-04-28
**Status:** Accepted

**Context.** The export-to-GIF feature is the viral mechanism. But shared GIFs could leak source code, env vars, secrets. Default-on full content would burn users.

**Decision.** `rewind export` masks file contents to first/last 8 lines and redacts env-shaped values by default. `--no-mask` opts out explicitly.

**Rationale.**
- Privacy is a one-way ratchet — a leaked GIF can't be unleaked.
- The viral demo is still strong with masked content (timeline + cost + tool names + structure).
- "Privacy-first export" is a marketing strength, not a weakness.

**Consequences.** Some users will want the full thing for screenshots in tutorials. They use `--no-mask` consciously. Acceptable.

---

## ADR-007: TUI first, no web dashboard in V1

**Date:** 2026-04-28
**Status:** Accepted

**Context.** A web dashboard would be more shareable than a TUI. But it needs hosting, auth, sync, etc. Out of scope for a single dev shipping in 6 weeks.

**Decision.** TUI only in V1. Web dashboard considered for V2.

**Rationale.**
- TUI matches Max's audience (devs who live in the terminal).
- Zero hosting cost. Zero account creation friction.
- Export-to-GIF gives the "shareable" property without a web app.
- A web dashboard adds 4-6 weeks of work easily.

**Consequences.** Some non-dev managers won't see the value as easily. Acceptable — they're not the target.

---

## ADR-008: MIT license

**Date:** 2026-04-28
**Status:** Accepted

**Context.** Picking a license. Apache, MIT, GPL, AGPL all viable.

**Decision.** MIT, same as `spent`.

**Rationale.**
- Permissive. Maximum adoption.
- Same as `spent` — consistent across the ecosystem brand.
- No hosted-saas-leeching concern in V1 (it's local-only anyway).
- If someone forks and builds a cloud version, fine — that's a separate market.

**Consequences.** Anyone can fork and commercialize. We compete on trust, brand, and pace, not on license terms.

---

## ADR-009: Build-in-public on LinkedIn, one post per phase

**Date:** 2026-04-28
**Status:** Accepted

**Context.** Need to warm up the audience before launch without spamming.

**Decision.** Six LinkedIn posts, one per phase, ~weekly. Each post shows real progress with a screenshot/GIF and a small finding. Final launch post is post #7.

**Rationale.**
- 1 post/week is the proven cadence for Max's audience (per `project_linkedin_strategy`).
- Each post is an organic data point, not a hype machine.
- By launch day, followers are primed and the launch post lands harder.

**Consequences.** Project becomes public from day 1. Competitors could observe. Risk acceptable — execution beats secrecy in this category.

---

## ADR-010: V1 captures Claude Code only via official hooks

**Date:** 2026-04-28
**Status:** Accepted

**Context.** Could capture by parsing `~/.claude/projects/*/sessions/*.jsonl` post-hoc, or by hooks, or both.

**Decision.** Hooks only in V1. Post-hoc parsing of historical JSONL files considered for V1.5.

**Rationale.**
- Hooks give us before/after file content, which JSONL alone cannot. Without it, rollback is impossible.
- Hooks are official and stable.
- Adding JSONL backfill is a nice-to-have for converting "old" sessions.

**Consequences.** Existing sessions that pre-date rewind installation are not captured in V1. Add backfill in V1.5 if users ask.

---

## ADR-011: PyPI distribution name `rewindx`, CLI command `rewind`

**Date:** 2026-04-28
**Status:** Accepted

**Context.** Phase 0 verification found `rewind`, `chrono`, and `unwind` all
taken on PyPI and npm. The GitHub repo `loplop-h/rewind` is free.

**Decision.** Distribute on PyPI as `rewindx`. The console_script entry point,
binary name, repo, and brand stay `rewind`. Users install with
`pip install rewindx` and invoke `rewind ...`.

**Rationale.**
- Renaming the brand to a less-clear word (e.g. `chronowind`) costs more
  recognition than the slight friction of a different package name.
- Console scripts are independent of distribution names, so the user-facing
  command remains the canonical brand.
- This avoids ever calling our own product something cute that ages badly.

**Consequences.** README and docs all reference both names where ambiguous.
Future docs/announcements should consistently use `rewind` as the noun and
`rewindx` only when referring to the install line.

---

## ADR-012: Single matcher `*` for every Claude Code hook in V1

**Date:** 2026-04-28
**Status:** Accepted

**Context.** Claude Code's hook config has a `matcher` field that accepts a
literal tool name, a regex, or `*`. We could narrow each hook to only the
tools whose data we use.

**Decision.** Use `matcher: "*"` for every hook we register.

**Rationale.**
- Capture is cheap; we want a complete record. Skipping a tool because we
  don't currently render it still loses replay fidelity.
- Future analytics will be retroactive over old captures. A narrow matcher
  would make those analytics inconsistent across sessions.
- We can always derive narrower matchers later without re-collecting data.

**Consequences.** A few microseconds of hook latency on tools we don't show.
Tolerable. Storage is bounded by the truncate setting and content-addressed
dedup, so the "extra" events cost almost nothing on disk.

---

## How to add a new decision

1. Append a new section at the bottom.
2. Number sequentially (ADR-NNN).
3. Status: Proposed → Accepted → (optionally) Deprecated → Superseded.
4. If a new decision overrides an old one, mark the old one Superseded and link.
5. Keep the rationale crisp. The point of an ADR is to remind future-you why.
