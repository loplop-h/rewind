<!-- Thanks for taking the time to send a PR. Use the structure below; delete sections that don't apply. -->

## Summary

<!-- One paragraph: what this PR changes and *why*. Link to the issue it closes if any. -->

Closes #

## Changes

<!-- Bulleted list of the substantive changes. Skip "added a comma" type items. -->

-

## Tests

<!-- New tests added? Coverage delta? `pytest` output of relevant subset is fine. -->

## Breaking changes

<!-- "None" is the right answer 95% of the time. If yes, describe the migration path. -->

None.

## Checklist

- [ ] `python -m pytest` passes locally (coverage gate ≥ 85%)
- [ ] `python -m ruff check . && python -m ruff format --check .` clean
- [ ] `python -m mypy src/rewind` clean
- [ ] CHANGELOG updated under `[Unreleased]` if user-visible
- [ ] Docs updated if behaviour changed
