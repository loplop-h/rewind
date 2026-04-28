# Launch Playbook

> Coordinated launch day. Tuesday or Wednesday morning Barcelona time. Single shot.

---

## Pre-launch (last week before launch)

### Beta program (30-50 people)
- DM individually, not as a blast.
- Pull from: people who reacted/commented on the spent launch post, devs in your network using Claude Code.
- Message template (paraphrase, don't paste):
  - "Building rewind — time-travel debugger for Claude Code sessions. Closed beta. Want a heads up + early access? Will send install in a couple of days."
- For yes responses, send install instructions, ask for honest feedback.
- One soft ask: "If it's useful, would you upvote on HN/comment on LinkedIn the day I launch?"

### Pre-warm content
Six build-in-public posts (one per phase) have already primed the audience over 6 weeks. By launch day, your followers should know the project exists and be curious.

### Assets to prepare 48h before launch
- [ ] Hero GIF: 30 seconds, the one demo
- [ ] Secondary GIF: rollback in action
- [ ] Tertiary GIF: export to share
- [ ] README polished, screenshots embedded
- [ ] Landing page live with one CTA: install command
- [ ] All launch posts pre-drafted, scheduled or queued
- [ ] PyPI v0.1.0 published, install verified clean on a fresh VM
- [ ] DM list of beta testers organized for launch-day pings

---

## Launch day (T-day)

### 07:00 Barcelona — final checks
- Verify install on a fresh machine (Mac, Linux, Windows if possible)
- Pull the repo, run `pip install rewind` from PyPI, run a session
- Make sure landing page resolves
- Verify tweet thread is composed and ready

### 08:00 Barcelona (02:00 ET) — internal soft launch
- Tag v0.1.0 release on GitHub with full release notes
- Smoke test the release artifact

### 09:00 Barcelona (03:00 ET) — staging
- Final read-through of all posts
- Refresh the demo GIF if it's been compressed badly anywhere

### 13:00 Barcelona (07:00 ET) — Show HN goes live first
- HN title: `Show HN: rewind – Time-travel debugger for Claude Code sessions`
  - Note: don't include emojis, marketing copy, or "the future of AI" framing — HN hates it
- HN body (~150 words):
  - Three sentences: what it does, why I built it, what it's missing.
  - One link to GitHub. No others.
  - Quick mention of license, no roadmap fluff.
- Submit. Lurk for 30 mins. Reply to first 3 comments fast and substantively.

### 13:30 Barcelona (07:30 ET) — Reddit
- r/LocalLLaMA: "I built a time-travel debugger for Claude Code sessions. Open source."
- r/SideProject: more casual framing — "spent 6 weeks on this, would love feedback"
- r/MachineLearning: only if there's a research-y angle. Otherwise skip.
- r/ClaudeAI: direct relevance, mention compatibility explicitly
- Each post should be its own genuine framing, not a copy-paste

### 14:00 Barcelona (08:00 ET) — Twitter / X thread
- 8-10 tweets, each ~200 chars
- Tweet 1: hook with the GIF
- Tweets 2-4: one feature each with screenshot
- Tweet 5-6: install + GitHub link + ask for stars
- Tweet 7-8: what's next, what's not in V1, license
- Tweet 9: thanks beta testers (tag them where appropriate)
- Tweet 10: bonus — an "ask me anything in the replies"

### 14:00 Barcelona — LinkedIn post (your formula)
- Use the proven posting formula from `project_linkedin_strategy`:
  1. Open with surprising personal metric (e.g. "Yesterday I spent $4 on a Claude Code session and broke 6 files. I rolled back in 3 seconds.")
  2. One-sentence bridge to the product
  3. 5-6 scannable bullets of what it does
  4. Anti-friction line ("local only, no API keys, no telemetry")
  5. **Personal finding** (the engagement driver) — what rewind revealed about your own sessions
  6. 2-line install
  7. NO link in body. Hashtags at bottom. GitHub link in first comment.
- Post time: 14:00 Barcelona = 8 AM ET (proven peak window)

### 14:15 — first-comment link drop
- Drop the GitHub URL as the first comment on your LinkedIn post
- Tag 2-3 close peers who agreed to engage early

### 14:30 — Product Hunt (optional)
- Submit only if hero GIF is genuinely great and beta showed strong signal
- Otherwise skip — PH costs energy that could go to HN/Reddit

### 15:00-23:00 — engagement window
- Refresh HN every 5-10 minutes
- Reply to every comment substantively, no boilerplate
- Reply to every Reddit comment within 1 hour
- Reply to every LinkedIn comment same day, ideally within 30 min
- Take screenshots of milestones (front page HN, etc.) for follow-up posts

### 23:00 — wrap and review
- Note total stars at end of day 1
- Note install count from PyPI stats
- Note any patterns in feedback

---

## Day 2-7 — sustained engagement

- Daily LinkedIn micro-posts: "rewind day 2: 800 stars, here's the most surprising bug report"
- Reply to every issue / PR within 24h, ideally within 4h for the first week
- If HN didn't hit front page, do one focused retry on day 3-4 with a different angle (only if there's a legitimate update)
- Submit to awesome lists: awesome-claude-code, awesome-mcp, awesome-cli, awesome-python
- DM-pitch 5-10 AI / dev tool newsletter writers personally

---

## Post-templates (drafts)

### LinkedIn launch post (template — adapt to actual numbers)

```
Yesterday I spent $4.20 on one Claude Code session.
The agent rewrote 6 files. Two of them broke production.

I built rewind to fix this exact moment.

Six weeks later it does:
- Captures every tool call, file edit, prompt, and cost
- Lets you scrub the session like a video — TUI timeline, key-by-key
- Rolls back files to any point in 3 seconds
- Exports the whole session as a 60-second GIF you can share

Today: 100% local, no API keys, no telemetry, MIT license.

The thing I didn't expect:
Once you can scrub through your own sessions, you start spotting patterns
in how YOU prompt Claude — not just what Claude does. My input phrasing
predicted the cost of a session better than the model setting did.

Two commands to try it:
pip install rewind
rewind cc setup

#ClaudeCode #OpenSource #DevTools #AI #Python
```

(GitHub link in first comment, not body)

### HN Show post (template)

```
Title: Show HN: rewind – Time-travel debugger for Claude Code sessions

Body:
Hi HN. I built rewind because I kept losing track of what my Claude Code
agent did during long sessions. Logs are JSONL, git diff shows files but
not the reasoning, and there's no way to roll back when the agent breaks
something subtle.

rewind hooks into Claude Code, captures every event and file change,
and gives you a TUI to scrub through. You can roll back the file system
to any point in the session ("goto event 31") and export the whole
session as a 60-second GIF.

Local-only, MIT license, no telemetry. Python 3.11+.

Repo: github.com/<user>/rewind

Happy to answer questions and would love feedback on the rollback safety
defaults — that's the part I expect to iterate on most.
```

### Twitter thread opening tweet

```
I built a time-travel debugger for Claude Code sessions.

Open source, local only, exports your session as a 60s GIF.

[hero GIF]

→ thread
```

---

## Metrics to track on launch day

| Metric | Target Day 1 | Stretch |
|--------|-------------:|--------:|
| GitHub stars | 1,000 | 5,000 |
| HN front page | yes | top 10 |
| LinkedIn impressions | 30,000 | 100,000 |
| Reddit upvotes (sum across subs) | 200 | 1,000 |
| Twitter thread impressions | 50,000 | 200,000 |
| PyPI installs | 500 | 2,500 |
| Inbound DMs | 10 | 50 |

If Day 1 misses on stars but the discussion was high quality (deep comments, recruiters reaching out), that's still a win — don't optimize for vanity metrics.

---

## What not to do

- Don't pitch in DMs (memorialized rule from `feedback_no_pitch_dms`)
- Don't post on a Friday or weekend
- Don't include external links in the LinkedIn post body (proven 40-50% reach penalty)
- Don't reply with templates — every comment gets a real answer
- Don't argue with criticism on HN, just thank and engage
- Don't compare to existing tools negatively — frame as "different shape"
- Don't ship a half-baked feature on launch day — V1 must be tight, not broad
