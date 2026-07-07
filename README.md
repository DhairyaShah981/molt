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

- **v2 — targeted ablation:** run a small A/B task suite with individual UNCERTAIN rules removed. Ablate five rules with real budget instead of fifty with none.
- **v3 — capability diff:** rerun audits across model releases and publish what the new model made obsolete. A changelog of intelligence, expressed as deleted scaffold.

## License

MIT
