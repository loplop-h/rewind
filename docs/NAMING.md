# Naming

> Working name: `rewind`. Final name TBD after availability check (Phase 0).

---

## Constraints

A good name for this product:

- **Verb-y / action-oriented.** It does something to your session.
- **Short.** ≤ 8 characters ideal.
- **Pronounceable in English and Spanish.** (Max's two main audiences.)
- **PyPI / npm / GitHub all available.**
- **Domain available** in `.dev`, `.tools`, or `.ai` at minimum.
- **Not already a known product / library** in the dev tools or AI space.
- **Easy to type.** No special characters, no double letters that get auto-corrected.

---

## Candidates (ranked)

### 1. `rewind`
- **Pros:** Verb. Clear. Universally understood. Strong metaphor (rewind a tape, rewind a session). Translates clean.
- **Cons:** Common word, likely taken on PyPI / npm / many domains.
- **Verify:**
  - PyPI: `https://pypi.org/project/rewind/`
  - GitHub repo `rewind` (org-level): possibly squatted
  - Domains: `rewind.dev`, `rewind.tools`, `rewind.ai`
  - Known products: rewind.ai exists (Mac memory tool, founded 2022). Conflict risk for branding clarity even if PyPI name is free.

### 2. `chrono`
- **Pros:** Time-oriented. Short. Distinctive. Works in EN/ES. Less crowded than rewind.
- **Cons:** Not as instantly intuitive. Used in some libraries (Rust `chrono` crate).
- **Verify:**
  - PyPI: `https://pypi.org/project/chrono/`
  - GitHub
  - Domains: `chrono.dev`, `chrono.tools`

### 3. `unwind`
- **Pros:** Verb. Implies undo / unraveling. Less crowded than rewind.
- **Cons:** Slightly less obvious metaphor for "session replay."
- **Verify:**
  - PyPI: `https://pypi.org/project/unwind/`
  - GitHub
  - Domains: `unwind.dev`

### 4. `reverse`
- **Pros:** Clear. Verb.
- **Cons:** Too generic — competes for SEO with reverse arrays, reverse engineering, etc.

### 5. `tape`
- **Pros:** Strong metaphor (record/play/rewind tape). Short. Memorable.
- **Cons:** Generic. Already a Node test framework. Could conflict.

### 6. `agentape`
- **Pros:** Distinctive. Combines agent + tape.
- **Cons:** Unusual to read. Looks like "agent ape" → wrong association.

### 7. `flux`
- **Pros:** Time-oriented (flux capacitor, Back to the Future). Short. Memorable.
- **Cons:** Already used heavily (Flux state library, GitHub Flow, etc.). High collision risk.

### 8. `scrub`
- **Pros:** Direct verb (you scrub through a video). Short.
- **Cons:** Has connotations beyond tech (e.g., cleaning, fitness). Slightly off-brand.

### 9. `replay`
- **Pros:** Clear. Verb.
- **Cons:** Very common word. Likely all variants taken.

---

## Ecosystem fit check

The four products in Max's open-source toolchain so far have these characteristics:

| Product | Verb-y? | Length | Tone |
|---------|--------|-------:|------|
| spent   | yes (past tense) | 5 | casual, sharp |
| debtx   | no (compound) | 5 | technical |
| mcpguard | no (compound) | 8 | functional |
| **TBD** | yes ideal | 5-7 | sharp, memorable |

`rewind` fits the tone best. `chrono` second. The others either don't match the brand or have too much collision risk.

---

## Decision rule

1. If `rewind` is available on PyPI and `rewind.dev` is available → use `rewind`.
   - The rewind.ai product is a different product (Mac memory) — coexistence is acceptable as long as PyPI / GitHub / one .dev domain land.
2. Else if `chrono` is available on PyPI → use `chrono`.
3. Else use `unwind`.
4. Reserve the chosen PyPI name immediately (publish stub `0.0.1`).

---

## Verification commands (run during Phase 0)

```bash
# PyPI
curl -s -o /dev/null -w "%{http_code}\n" https://pypi.org/project/rewind/
# 200 = taken, 404 = available

# GitHub user repo
gh repo view loplop-h/rewind 2>&1 | head -1

# npm (defensive)
curl -s -o /dev/null -w "%{http_code}\n" https://registry.npmjs.org/rewind

# Domains
whois rewind.dev | grep -i "domain status\|registry expiry"
whois rewind.tools | grep -i "domain status\|registry expiry"
```

---

## Branding notes

Whatever name we pick:

- Logo: a simple monospace wordmark. Optional glyph: a counter-clockwise arrow or a tape symbol.
- Color: dark terminal palette. Accent: muted teal or amber (matches `spent`'s aesthetic).
- Tagline candidates:
  - "Time-travel for your AI coding sessions."
  - "Scrub. Diff. Rollback."
  - "Strava for AI coding."
- Pronunciation guide on the README footer (just for fun): `/riːˈwaɪnd/`.

---

## What we won't do

- Won't pick a name that requires explanation.
- Won't pick a made-up word ("zorvix", "aigent") — too startup-pitch-deck.
- Won't pick a name with intentional misspellings ("rwnd").
- Won't ship until the name is locked. Renaming a published package is painful.
