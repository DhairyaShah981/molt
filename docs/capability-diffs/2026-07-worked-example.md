# Capability diff: worked example (author's own transcripts, July 2026)

This is the dogfood run that shipped with molt v0.3.0 — a worked example of the
method on the author's machine, not a headline finding. The author's global
scaffold is deliberately tiny (4 auditable rules, ~374 tokens), so treat this as
"here is what the output looks like" and run it on your own 40-rule CLAUDE.md,
where the story will be bigger.

**Author setup:** 4 rules across `~/.claude/CLAUDE.md` + one `@import`,
80 old-era / 513 new-era sessions, era boundary 2026-06-10 (frontier model
release used as the switch date).

## Raw diff

```
# molt capability diff

Old era: 80 sessions · New era: 513 sessions · 2 verdicts changed, 2 unchanged.

| rule | from → to | reading |
|---|---|---|
| ⚠️ Name collision: If `rtk gain` fails, you may have reachi… | DEAD → LOAD_BEARING | subject now arises and rule steers it |
| Use the `/browse` skill from gstack for all web browsing. Never… | DEAD → LOAD_BEARING | subject now arises and rule steers it |
```

## What I'm deleting

Nothing on this evidence. No rule went `* → DEAD`, so no internalization claim
can be made from this window.

## What I'm keeping

Both transitions are `DEAD → LOAD_BEARING` — rules whose subject started
*arising* in the new era. Per the honesty rules, that pattern is explained by
the author's work changing (heavier browser/tooling use in recent months), not
by the model changing. This is exactly the confound the how-to warns about.

## Caveats

- 80 vs 513 sessions — imbalanced eras.
- 4 rules is far too small a scaffold to say anything about internalization;
  the method needs a rule-heavy config to produce interesting `→ DEAD` rows.
- Era boundary chosen by model release date, but the author also changed
  projects around then. Confounded, disclosed.

**The ask:** if your CLAUDE.md has dozens of battle-scarred rules and you've
been through a model upgrade, run the three commands in the
[how-to](README.md) and PR your diff here.
