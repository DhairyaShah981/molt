# Changelog

## 0.2.0 — 2026-07-08

### Added
- `molt ablate` (v2): causal A/B testing of individual rules against a task
  suite via `claude -p` in sandbox dirs. Verdicts: CARRIES_WEIGHT / NO_EFFECT /
  HARMFUL. Model-agnostic engine (injectable trial runner), fully unit-tested
  without model calls.
- `molt diff` (v3): capability diff between two `audit --json` reports —
  verdict transitions with interpretations, internalization candidates,
  added/removed rules.
- `molt audit --json` machine-readable output.
- `molt audit --since/--until` to slice sessions by era (first-message
  timestamp, mtime-independent).
- Diff integration contract in the eval harness (era split over fixtures,
  hand-derived expected transitions).

### Fixed
- "1 rules" pluralization in reports.
- Unhelpful error when the current directory has no transcripts — now hints
  `--all-projects` / `--transcripts DIR`.
- Rules spanning wrapped bullet lines now carry their full line range
  (`end_line`), so ablation strips the whole rule, not just its first line.

## 0.1.0 — 2026-07-07

Initial release: `molt scan`, `molt audit` (DEAD / IGNORED / UNCERTAIN /
LOAD_BEARING verdicts mined from Claude Code transcripts), optional
`--judge`, labeled-fixture eval harness, CI.
