# Changelog

## 0.3.0 — 2026-07-08

### Added
- `molt prune` (v4): act on the audit. Dry run by default (evidence table of
  what would be deleted and why), `--apply` edits the files, `--pr` applies on
  a fresh branch and opens a pull request whose body carries the receipts.
  Prunes DEAD rules only unless `--include-ignored`; LOAD_BEARING and
  UNCERTAIN are never touched. Multi-rule deletion is bottom-up per file so
  line ranges stay valid, and wrapped (multi-line) rules are removed whole.
- Public capability diffs (v5): `docs/capability-diffs/` — how-to, honesty
  rules (era confounds, sample sizes, observational-not-causal), a publishable
  template, and a first worked example generated from the author's own 593
  sessions. Community diffs accepted by PR.
- Prune contract in the eval harness: on the fixtures, exactly the two
  ground-truth DEAD rules are prunable and survivors stay intact.

### Changed
- Session loading is shared between `audit` and `prune` (same discovery,
  hints, and era-slice behavior).

### Hardened (pre-ship adversarial review findings)
- `molt prune` refuses the global `~/.claude/CLAUDE.md` unless `--all-projects`
  is set — pruning it on one project's evidence would delete rules that are
  load-bearing in other projects that were never audited.
- File edits are atomic (temp file + `os.replace`) so a crash mid-write can't
  leave a scaffold file truncated.
- `molt prune --pr` checks every precondition (single repo, `gh` installed,
  clean worktree) before any mutation, checks each git step's return code, and
  restores your original branch if `add`/`commit` fails — no more pushing a
  branch that lacks the prune commit or stranding you on a temp branch.

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

### Hardened (pre-ship adversarial review findings)
- `molt ablate` refuses the global `~/.claude/CLAUDE.md` — `claude -p` loads it
  in both trial arms, which would make every verdict read NO_EFFECT.
- Ablation parses only the target file (no `@import` following), so imported
  rules can't be stripped with wrong line numbers.
- Agent-invocation failures are a third trial state (errored): excluded from
  pass rates, counted per rule, and flagged in the report.
- `--since`/`--until` disable the session load limit so old eras aren't
  silently starved out of capability diffs; malformed dates are rejected;
  sessions without timestamps are reported when dropped.
- Tasks files are validated (non-empty list of `{prompt, check}`) with real
  errors instead of a stripable `assert`; runs >100 require `--yes`.
- `molt diff` validates its inputs and reports carry a `molt_report` schema
  marker; rule text is pipe-escaped in all markdown tables.
- Sandbox trials pass `--permission-mode acceptEdits` so file-writing tasks
  actually run non-interactively.

## 0.1.0 — 2026-07-07

Initial release: `molt scan`, `molt audit` (DEAD / IGNORED / UNCERTAIN /
LOAD_BEARING verdicts mined from Claude Code transcripts), optional
`--judge`, labeled-fixture eval harness, CI.
