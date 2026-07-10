# Public capability diffs

A **capability diff** is a changelog of model intelligence, expressed as scaffold
your instructions no longer need. When a new model ships, the interesting question
isn't its benchmark score — it's *which of your crutches it just made obsolete*.
Labs measure this internally and never publish it. You can.

## Publish your own

1. Pick the release date of the model you switched to (call it `D`).
2. Slice your own transcripts into eras and audit each:

```bash
molt audit --all-projects --limit 0 --until D --json --out old-era.json
molt audit --all-projects --limit 0 --since D --json --out new-era.json
molt diff old-era.json new-era.json
```

3. Read the transitions:

| transition | reading |
|---|---|
| `LOAD_BEARING → DEAD` | **the headline** — a rule that used to steer behavior stopped being exercised; candidate internalization |
| `IGNORED → LOAD_BEARING` | the new model started complying with a rule the old one ignored |
| `LOAD_BEARING → IGNORED` | regression — compliance dropped on the new model |
| `DEAD → LOAD_BEARING` | your work changed, or the model now hits situations it didn't before |

4. Write it up and PR it into this directory as `YYYY-MM-<model>.md`.

## Honesty rules

- **Say your sample sizes.** 12 old-era sessions vs 500 new-era sessions is a
  confounded comparison — say so.
- **Eras confound model + work.** Your projects changed between eras too. A
  `DEAD → LOAD_BEARING` transition usually means *your work* changed, not the
  model. Only claim internalization for `* → DEAD` transitions on rules whose
  subject still arises in the new era.
- **Observational, not causal.** For a rule you're about to delete on diff
  evidence, run `molt ablate` on it first if it matters.
- **Redact before publishing.** Your rule texts are going public — read them.

## Template

```markdown
# Capability diff: <old model> → <new model>

**Author setup:** <N> rules across <files>, <old sessions> old-era /
<new sessions> new-era sessions, era boundary <date> (<model> release).

## Raw diff
<paste `molt diff` output>

## What I'm deleting
<rules going DEAD whose subject still arises — with the evidence>

## What I'm keeping
<transitions explained by work changes, not model changes>

## Caveats
<sample sizes, confounds, anything thin>
```

Published diffs live in this directory. First one: [2026-07-worked-example.md](2026-07-worked-example.md).
