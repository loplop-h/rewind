# rewind — Project Plan

> Time-travel debugger and shareable replay for Claude Code sessions.
> Working name: `rewind`. May change after PyPI/GitHub availability check.

---

## One-liner
Capture every Claude Code event, scrub through the timeline, roll back files to any point, export the session as a 60-second video to share.

## The pitch (LinkedIn-ready)
> "Claude Code does 47 tool calls in a session. You see only the final state. rewind shows every decision in between, lets you scrub back to any point, and exports the whole session as a 60-second GIF you can share."

## Why this product

Four reasons in priority order:

1. **Closes the ecosystem.** spent (cost), debtx (quality), mcpguard (security) already exist. rewind is the missing fourth: observability + recovery. Once shipped, the four together tell one coherent story: an open-source toolchain for Claude Code.
2. **Universal pain, no decent solution.** Anyone using Claude Code, Cursor, Aider, or Codex has had the "agent changed something I can't trace" moment. The native session JSONL is unreadable. `git diff` shows file changes but not the *thinking*. Nobody bridges this gap well.
3. **Visual wow factor.** A TUI timeline with scrub + diffs + rollback is one of the most demo-able dev tools possible. The 30-second screen recording sells itself.
4. **Built-in distribution loop.** The export-to-GIF feature turns every user into a marketing channel. People will share their replays because they look good. Like Strava, but for AI coding sessions.

## Two viral hooks (different audiences)

- **Technical:** "Time-travel debugger for AI coding sessions. Scrub, diff, rollback."
- **Broad:** "Strava for AI coding. Share what your agent built in 60 seconds."

## Core features (MVP scope)

| # | Feature | Why it matters |
|---|---------|----------------|
| 1 | Capture all hook events to local SQLite | Foundation. Without this nothing else works |
| 2 | Content-addressed file snapshots (before/after each Edit/Write) | Enables rollback |
| 3 | Rich-based TUI: timeline + detail pane + diff viewer | The wow demo |
| 4 | Scrub navigation: ↑↓→ keys to walk events | UX core |
| 5 | `rewind goto <event>` — rollback file system to any point | Killer feature for "agent broke things" |
| 6 | `rewind export --gif` — render session to a 30-90s video | The viral mechanism |
| 7 | Cost / token analytics overlay | Direct value, ties into spent's audience |
| 8 | One-command setup: `rewind cc setup` configures Claude Code hooks | Friction = death |

## Explicitly out of scope (V1)

- Process/memory rollback (impossible without forking)
- Multi-user / cloud sync
- Live streaming during a session (post-hoc only in V1)
- Editor plugin (CLI/TUI only)
- Real-time collab on a session
- Web app dashboard (maybe V2)
- Privacy-first encrypted storage (default local only is enough)

## Stack

- **Python 3.11+** — same toolchain as spent, zero curve
- **Click** — CLI framework
- **Rich** — TUI rendering
- **SQLite** — single-file event store, no daemon
- **PIL + imageio** — GIF/MP4 export
- **pytest** — testing, 80%+ coverage target
- **uv** — fast install / dev (optional)
- **MIT license** — same as spent

## Success criteria

| Metric | 7-day target | 30-day target |
|--------|-------------:|--------------:|
| GitHub stars | 1,000 | 5,000 |
| HN front page | Yes | n/a |
| LinkedIn impressions on launch post | 30,000+ | n/a |
| Shared replay GIFs (organic) | 50 | 500 |
| PyPI downloads | 2,000 | 15,000 |
| Inbound recruiter / partnership DMs | 5 | 25 |

## Anti-goals (what would kill the project)

- Shipping before the demo GIF is great
- Adding features V1 doesn't need
- Generic "AI agent" framing — must be Claude Code-first to win
- Cloud-first — must be local-first for trust

## Documents

- [ROADMAP.md](docs/ROADMAP.md) — 6-week phase plan
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — schemas, data flow, modules
- [LAUNCH.md](docs/LAUNCH.md) — pre-launch + launch day playbook
- [DECISIONS.md](docs/DECISIONS.md) — decisions log (ADR-style)
- [NAMING.md](docs/NAMING.md) — name candidates + verification

## Owner & cadence

- **Owner:** Max
- **Cadence:** sin prisa — quality over speed. ~6 weeks calendar, ~80-120 hours actual work.
- **Build-in-public:** ~1 LinkedIn post per phase (6 posts) showing progress. Final launch post when shipped.
