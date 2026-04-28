# Launch copy — rewind v0.1.0

> Drafts of every launch post for Wednesday morning Barcelona time. Adjust
> numbers and emoji preferences before posting. **No external links in the
> LinkedIn body** — link in first comment.

---

## 1. LinkedIn post (14:00 BCN  =  8 AM ET)

Open with a personal data point, bridge to the product, scannable bullets,
finish with the install. No emoji. Hashtags at the bottom. GitHub link
goes in the first comment.

```
Yesterday Claude Code did 47 tool calls in one session.
Six of them broke things. I couldn't tell which six until I built rewind.

rewind is a time-travel debugger for Claude Code sessions.

What it does:
- Captures every prompt, tool call, file edit, and cost into a local SQLite
- Shows the full session as a timeline you can scrub
- Rolls back the file system to any point in 3 seconds
- Exports the session as a privacy-masked Markdown transcript
- Local-only. No API keys. No telemetry. MIT licensed.

What surprised me running it on my own sessions:
- The wasted tool calls cluster — when one fails, three more usually follow
- 28% of my tool calls produce zero code (Read/Grep before each Edit)
- I can spot bad prompts now because they make the timeline noisy

Two commands to try it:
pip install rewindx
rewind cc setup

#ClaudeCode #OpenSource #DevTools #AI #Python
```

**First comment (drop ~1 minute after posting):**
```
GitHub: github.com/loplop-h/rewind
```

---

## 2. Show HN (~13:00 BCN, before LinkedIn so HN warms up first)

Title (under 80 chars, no emoji, no clickbait):
```
Show HN: rewind – Time-travel debugger for Claude Code sessions
```

Body (under ~200 words, sober, links only at the end):
```
Hi HN. I built rewind because I kept losing track of what my Claude Code
agent did during long sessions. The agent's transcripts are JSONL, hard
to read, and impossible to replay. `git diff` shows the files that
changed but not the reasoning. When the agent broke something subtle, I
had nothing to fall back on.

rewind hooks into Claude Code, captures every event and file change into
a per-session SQLite store with content-addressed file snapshots, and
gives you a TUI to scrub through. You can roll back the file system to
the state just before any event ("goto event 6") and it creates a
checkpoint first so `rewind undo` reverses it.

It's local-only by default — zero network calls, no telemetry. The
exporter masks file contents and env-shaped secrets unless you pass
--no-mask. MIT license.

The thing I wasn't expecting: once you see your sessions on a timeline,
you start spotting patterns in your own prompting, not just the agent's
output.

131 tests, 87% branch coverage, mypy strict. Python 3.11+ on
linux/macos/windows.

Repo: https://github.com/loplop-h/rewind

Happy to take feedback, especially on the rollback safety defaults.
```

---

## 3. Reddit posts (~13:30 BCN)

### r/ClaudeAI

Title:
```
I built a time-travel debugger for Claude Code sessions (open source)
```

Body:
```
Got tired of not being able to tell which tool call broke things during
long Claude Code sessions, so I built rewind.

It hooks into Claude Code, captures every event into a local SQLite,
shows you the timeline, and lets you roll back the file system to any
point with a single command. There's a checkpoint before each rollback
so undo is one keystroke.

Local-only. No API keys. No telemetry. MIT license. Python 3.11+.

GitHub: https://github.com/loplop-h/rewind
PyPI:   pip install rewindx   (binary is `rewind`)

Hero shot of the TUI: [link to docs/images/hero.png on github]
Demo of goto + undo: [link to docs/images/rollback.gif on github]

Happy to answer questions. Curious whether other people would actually
share their session GIFs publicly — that's where the export feature is
heading next.
```

### r/LocalLLaMA

Title:
```
Open-source replay tool for Claude Code (local, no telemetry)
```

Same body as r/ClaudeAI, slightly different opening sentence: lead with
"open-source" and "local" rather than the personal frustration angle.

### r/SideProject

Title:
```
Spent 3 days building a time-travel debugger for AI coding sessions
```

Body — lead with the build story (sub readers love this):
```
Stack: Python 3.11+, Click, Rich, SQLite (WAL), content-addressed blob
store. 131 tests, 87% coverage, mypy strict, multi-OS CI.

Why I built it: every Claude Code session I run does dozens of tool
calls. When something breaks, the JSONL transcripts are useless and
git diff doesn't tell you which call broke what. rewind captures
everything, shows it as a timeline, lets you roll back the file system
to any point.

What was harder than expected: the rollback engine. Snapshots are
content-addressed (sha256 → blob, like git's object store) so dedup is
free, but deciding "did this file exist before this event ran" took a
couple of iterations to get right.

What I'm proudest of: zero network calls, ever. No telemetry, no cloud.
A session lives entirely in ~/.rewind/sessions/<id>/ and you can
delete it with rm -rf.

GitHub: https://github.com/loplop-h/rewind
```

### r/MachineLearning

Skip unless we have a research-grade benchmark to share. Otherwise we
look like noise. Plan to revisit when we have V0.2 with the export GIF
working.

### Lobsters (~12:30 BCN, before Show HN)

Lobsters has an invite-only audience that's heavy on systems / dev tools
people. A well-received post tends to cross-pollinate to HN within hours.

Submission URL: `https://github.com/loplop-h/rewind`
Title (≤ 100 chars): `rewind: time-travel debugger for Claude Code sessions`
Tags: `programming`, `practices` (or `python` if available — pick the two
most fitting at submission time)
Story text (optional; only if asked):
```
Open-source CLI that hooks into Claude Code, captures every prompt /
tool call / file edit / cost into a local SQLite event store with
content-addressed blob storage, and lets you scrub the session timeline
and `goto N` to roll the file system back to any prior point. Local
only, no telemetry, MIT.

The interesting bit is the rollback semantics: snapshots are
content-addressed (sha256 → blob, like git's object store) so dedup is
free, and each rollback creates a checkpoint so `rewind undo` reverses
it. Python 3.11+, runs on linux/macos/windows.
```

---

## 4. Twitter / X thread (~14:00 BCN, simultaneous with LinkedIn)

Each tweet ends with `(N/8)` so people know how long the thread is.

Tweet 1 — hook with the MP4 (preferred over GIF on Twitter for reach):
```
I built a time-travel debugger for Claude Code sessions.

Open source. Local only. Exports as a privacy-masked transcript.

Watch goto + undo land a 4-hour session in 3 seconds: ↓
[attach docs/images/demo.mp4]

(1/8) 🧵
```

Tweet 2:
```
Why?

Claude Code does 30-50 tool calls per session. The session JSONL is
unreadable. git diff shows files, not reasoning. When the agent breaks
something, you have nothing to fall back on.

rewind: capture → timeline → rollback.

(2/8)
```

Tweet 3 — the asset:
```
Every prompt, tool call, file edit, and cost lands in a local SQLite
store + content-addressed blob store. Per-session, single folder, no
daemon, no cloud.

[attach docs/images/hero.png]

(3/8)
```

Tweet 4 — privacy:
```
Zero network calls. No telemetry. The exporter masks file contents and
env-shaped secrets unless you pass --no-mask.

Trust is the asset for a tool that observes everything.

(4/8)
```

Tweet 5 — the "Strava" angle:
```
A full GIF/MP4 export backend lands in 0.2. Imagine sharing a 60-second
replay of a 4-hour Claude Code session. PR descriptions become videos.
Bug reports stop being one-line.

That's the long-term bet.

(5/8)
```

Tweet 6 — install + repo:
```
pip install rewindx
rewind cc setup

Python 3.11+. Linux / macOS / Windows.
136 tests, 87% branch coverage, MIT.

Repo: github.com/loplop-h/rewind

(6/8)
```

Tweet 7 — sister projects:
```
This is one corner of an open-source toolchain for Claude Code:

- spent     → cost tracking
- debtx     → code quality
- mcpguard  → MCP security
- rewind    → observability + recovery

(7/8)
```

Tweet 8 — call to action:
```
If you use Claude Code (or Cursor or Aider) and you've ever asked "what
did the agent just do" — try it and tell me what's missing.

Replies open.

(8/8)
```

---

## 5. Pre-launch DM template (Tuesday night, ~10 personas)

Send to people who reacted/commented on the spent launch. Personalize
the first line for each recipient.

```
hey [name] — quick one. launching rewind tomorrow at 14:00 BCN.
time-travel debugger for Claude Code sessions: timeline + goto + undo +
shareable export. open source, local-only, MIT.

heads up so you can grab it early if it looks useful:
pip install rewindx
rewind cc setup

if you find a bug or have an obvious feature ask, drop it in a DM here
and i'll have ~24h to land it before launch. no pressure to engage on
launch day — but if it's useful and you do feel like commenting, that
also helps a ton.

repo with full docs: github.com/loplop-h/rewind
```

Don't pitch. Don't oversell. Don't ask for upvotes explicitly — the soft
"if you do feel like commenting" is enough.

---

## 6. Order of operations (T = launch time = 14:00 BCN)

| T-       | Action                                                                  |
|----------|-------------------------------------------------------------------------|
| -24h     | DM beta list (~10 people)                                               |
| -2h      | Last smoke-test in fresh venv (`scripts/smoke_test_pypi.py`)            |
| -90m     | Verify CI green on main                                                 |
| -60m     | Verify GitHub Release page renders + topics show on repo card           |
| -90m     | Submit Lobsters (slow climb, want lead time)                            |
| -45m     | Final read-through of every post                                        |
| -10m     | Show HN drafted in browser, ready to submit                             |
| **T+0**  | Submit Show HN                                                          |
| T+10m    | Reply to first HN comment substantively                                 |
| T+15m    | Reddit posts (r/ClaudeAI, r/LocalLLaMA, r/SideProject)                  |
| T+20m    | Twitter thread + LinkedIn post                                          |
| T+22m    | Drop GitHub link as first comment on LinkedIn                           |
| T+30m    | Reply to first LinkedIn / Twitter comments                              |
| T+1h     | Check HN ranking; if not on `/new` first page, DM 2-3 friends to look   |
| T+3h     | Status post on LinkedIn: "Nh stars in 3 hours, here's what people ask"  |
| T+12h    | Awesome-list PRs (see awesome-list table below — pick currently open)   |
| Day 2    | Daily LinkedIn micro-post + issue triage                                |
| Day 3    | Product Hunt submission (only if Day 1 numbers warrant it)              |

---

## 7. Awesome-list submissions (post-launch, day 2-3)

Verified at the time of writing — re-check before submitting because TOCs shift.

| List                                              | Stars  | Status        | Action                                                |
|---------------------------------------------------|-------:|---------------|-------------------------------------------------------|
| `hesreallyhim/awesome-claude-code`                | 41.6K  | TOC in transition (skip until update lands) | Watch the repo and submit once the new TOC ships. Highest signal of any list. |
| `rohitg00/awesome-claude-code-toolkit`            | 1.5K   | Active        | Open PR adding rewind to the *developer tooling* / *observability* section. Pitch line: "Time-travel debugger and shareable replay for Claude Code sessions." |
| `ccplugins/awesome-claude-code-plugins`           | 735    | Active        | Open PR adding rewind under *hooks* (since rewind installs hooks via `rewind cc setup`). |
| `jqueryscript/awesome-claude-code`                | 317    | Active        | Open PR under *Tools / IDE / Frameworks*. |
| `punkpeye/awesome-mcp-servers`                    | 85.8K  | **Skip**      | rewind is not an MCP server. Wrong list. |

PR template (paraphrase to match the host list's existing entries):

```markdown
- [rewind](https://github.com/loplop-h/rewind) — Time-travel debugger
  for Claude Code sessions. Captures every prompt, tool call, and file
  edit into a local SQLite store; rolls the file system back to any
  prior point with `rewind goto N`; exports a privacy-masked Markdown
  transcript. Local-only, MIT.
```

## 8. Anti-checklist (do not do)

- Don't include external links in the LinkedIn post body (proven 40-50% reach penalty).
- Don't post on Friday or weekend.
- Don't reply with templates — every comment gets a real answer.
- Don't argue with criticism on HN — thank, engage, do not defend.
- Don't compare to existing tools negatively.
- Don't ship a half-baked feature on launch day. V0.1 is tight, that's the point.
- Don't pitch in DMs (memorialised rule).
