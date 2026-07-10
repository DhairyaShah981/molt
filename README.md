# molt 🪶

**The scaffold-debt auditor.** Everyone tells you to delete your agent scaffolding. Nobody tells you *which parts are safe to delete*. molt does — with evidence mined from your real session transcripts, at zero inference cost.

```
$ molt audit

Audited 42 rules (~2,100 tokens) against 200 real sessions.
Prunable: 17 rules (~900 tokens, 43% of your scaffold).

💀 DEAD      11 rules — never came up in any session. Pure tax.
🙈 IGNORED    6 rules — the situation arose; the agent did the opposite.
❓ UNCERTAIN  4 rules — mixed evidence, worth a targeted ablation.
🏗️ LOAD_BEARING 21 rules — actively steering behavior. Keep.
```

## Why

The "bitter lesson of agent harnesses" is now consensus: models keep internalizing what scaffolding used to do, so instruction files (CLAUDE.md and friends) rot into cargo cult. Context-rot research shows the bloat doesn't just cost tokens — it degrades compliance with the rules that *do* matter.

But everyone prunes by vibes. molt replaces vibes with receipts:

- Your agent CLI already logs every session (`~/.claude/projects/*.jsonl`).
- Those transcripts are thousands of natural experiments about which rules ever fire.
- molt parses your instruction files into atomic rules, greps every rule against every session, and classifies each one — **observationally, without a single model call**.

## Install

```bash
git clone https://github.com/DhairyaShah981/molt && cd molt
pip install -e .
```

Python 3.9+, stdlib only. No dependencies.

## Use

```bash
molt scan                 # inventory: rules + token cost (instant, static)
molt audit                # classify rules against this project's transcripts
molt audit --all-projects # mine every project's sessions
molt audit --judge        # LLM-judge the UNCERTAIN rules (uses `claude -p`)
molt audit --out report.md
```

By default molt auto-discovers `~/.claude/CLAUDE.md` and `./CLAUDE.md` (following `@import` lines), and reads transcripts from `~/.claude/projects/`. Point it elsewhere with explicit file args and `--transcripts DIR`.

### Targeted ablation (v2)

The audit is observational — for causal proof, ablate. Give molt a small task
suite and it A/Bs each rule with real agent runs (`claude -p` in a sandbox
dir, task's `check` shell command decides pass/fail):

```bash
cat > tasks.json <<'EOF'
[{"prompt": "create a hello-world python script and test it", "check": "test -f hello.py && python hello.py"}]
EOF
molt ablate ./CLAUDE.md --tasks tasks.json --rule "uv pip" --trials 5
```

Verdicts: `CARRIES_WEIGHT` (pass rate drops without the rule — keep),
`NO_EFFECT` (safe to delete), `HARMFUL` (pass rate *rises* without it — delete
fast). Trials where the agent invocation itself fails are counted as **errors**,
excluded from both rates, and flagged in the report — infrastructure noise never
masquerades as a verdict. Ablate the few rules the audit marked UNCERTAIN, not
all fifty — that's the economics the observational pass buys you.

Two guardrails to know about: molt refuses to ablate the **global**
`~/.claude/CLAUDE.md` (Claude loads it in *both* trial arms, so every verdict
would read NO_EFFECT — copy rules into a project CLAUDE.md instead), and each
task's `check` is a shell command executed with your full privileges — only run
tasks.json files you wrote or read.

### Capability diff (v3)

Same scaffold, two transcript eras (old model vs new model), diffed verdicts.
Rules that were LOAD_BEARING and became DEAD are your capability changelog —
scaffolding the new model no longer needs:

```bash
molt audit --until 2026-06-01 --json --out old.json   # era: before the model upgrade
molt audit --since 2026-06-01 --json --out new.json   # era: after
molt diff old.json new.json
```

Publishing your diff is the point — see [docs/capability-diffs](docs/capability-diffs/README.md)
for the how-to, honesty rules, and template. PRs welcome.

### Auto-prune (v4)

Act on the audit. `molt prune` deletes rules the evidence condemns — dry run by
default, receipts always:

```bash
molt prune                # dry run: what would be deleted, with evidence
molt prune --apply        # edit the files
molt prune --pr           # apply on a new branch and open a PR carrying the evidence
molt prune --include-ignored   # also prune IGNORED rules (default: DEAD only)
```

Only DEAD rules are pruned by default. IGNORED rules need the explicit flag —
sometimes an ignored rule should be *enforced*, not deleted. LOAD_BEARING and
UNCERTAIN are never touched.

## How verdicts work

Each rule gets signals (backticked commands/tools beat prose keywords) and is matched — word-boundary safe — against three surfaces per session: user text, assistant text, and *actions* (bash commands + tool calls).

| verdict | meaning |
|---|---|
| 💀 `DEAD` | subject never appeared in any audited session |
| 🙈 `IGNORED` | prohibition violated in actions, or mandate's subject discussed but never executed |
| ❓ `UNCERTAIN` | complied sometimes, skipped more often — ablation candidate |
| 🏗️ `LOAD_BEARING` | evidence the rule steers real behavior |

Verdicts are **observational lower bounds**. A DEAD rule might cover a situation that hasn't occurred yet; an IGNORED prohibition might be violated for good reasons. molt brings evidence, you make the call.

## Evals

The classifier is contract-tested against hand-labeled fixtures covering every verdict class:

```bash
python tests/test_molt.py   # unit tests
python evals/run_evals.py   # labeled-fixture evals — must be 100%
```

CI runs both on every push. If you find a transcript pattern molt misclassifies, PR it as a fixture — the eval suite is the spec.

## Honest limitations

- **Single-rule matching only.** Rules that interact (A useless alone, load-bearing with B) are invisible to v1.
- **Signal extraction is lexical.** A rule with no greppable terms ("be concise") can't be audited observationally — use `--judge`.
- **Survivorship bias.** Transcripts show what happened *with* the rule in place. IGNORED is strong evidence; LOAD_BEARING is weaker. Causal proof needs ablation (v2).

## Roadmap

- ~~v2 — targeted ablation~~ shipped (`molt ablate`)
- ~~v3 — capability diff~~ shipped (`molt audit --json` + `molt diff`)
- ~~v4 — auto-prune PRs~~ shipped (`molt prune --pr`)
- ~~v5 — public capability diffs~~ shipped ([docs/capability-diffs](docs/capability-diffs/README.md) — send yours)
- **v6 — PyPI release** (`pip install molt-audit`) once the community diff loop proves out.

## License

MIT
