# Contributing to rewind

Thanks for your interest in helping. This file covers what you need to know
before opening a PR.

## Development setup

Requires Python 3.11+.

```bash
git clone https://github.com/loplop-h/rewind
cd rewind
python -m venv .venv && source .venv/bin/activate    # or .venv\Scripts\activate on Windows
python -m pip install -e ".[dev]"
```

## Daily workflow

```bash
python -m pytest                       # full test suite + coverage gate
python -m ruff check .                  # lint
python -m ruff format --check .         # format check (use without --check to fix)
python -m mypy src/rewind               # type check
```

The CI pipeline runs all four. PRs that fail any of them won't be merged.

## Quality bars

- **Coverage:** ≥ 85 % branch coverage on the whole package. The pyproject.toml
  enforces this via `--cov-fail-under=85`.
- **Lint:** ruff with the rules selected in `pyproject.toml`. No noqa unless the
  reason is documented inline.
- **Types:** mypy in strict mode, no `Any` returns, no implicit Optional.
- **Tests:** pytest. Unit tests in `tests/unit`, end-to-end and CLI tests in
  `tests/integration`. Use the fixtures in `tests/conftest.py` (`rewind_home`,
  `config`, `manager`, `workspace`, `make_payload`) instead of rolling your own.

## Style

- File size: ~200–400 lines is the sweet spot, ~800 the hard ceiling. Split
  modules before they sprawl.
- Prefer small frozen `dataclass(slots=True, kw_only=True)` over plain dicts at
  module boundaries.
- No emoji in source, comments, or docs unless explicitly requested.
- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`,
  `chore:`, `perf:`, `ci:`.

## Adding a new feature

1. Open an issue describing the user-visible change and the trade-offs you
   considered. Link to the relevant ADR(s) in `docs/DECISIONS.md`.
2. Write tests first. Aim for failing tests before any new code lands.
3. Implement the smallest change that passes the tests.
4. If your feature changes user-visible behaviour, update `CHANGELOG.md` under
   the "Unreleased" section.
5. Run the full pipeline locally before opening the PR.

## Adding an ADR

When you make a design decision that future-you might second-guess, drop an
ADR at the bottom of [docs/DECISIONS.md](docs/DECISIONS.md). Keep it short:
context, decision, rationale, consequences. The ADRs in that file already are
good templates.

## Releasing

(Maintainers only.) Tag with `vX.Y.Z`, push, the CI builds the wheel and
sdist. PyPI uploads happen manually with `python -m build && python -m twine
upload dist/rewindx-X.Y.Z*`.
