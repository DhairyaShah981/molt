"""v2 — targeted ablation.

The observational audit (evidence.py) gives lower-bound verdicts for free.
For the handful of rules it can't settle, ablation buys causal evidence:
run the same task suite with and without one rule, compare pass rates.

The engine is model-agnostic: callers supply trial_runner(scaffold_text,
task) -> bool. Tests inject a deterministic fake; the CLI injects a real
`claude -p` runner that executes each task's shell `check` in a sandbox
directory. Ablate FEW rules with real trials, not many with none — that's
the whole economics lesson of v1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .rules import Rule

CARRIES_WEIGHT = "CARRIES_WEIGHT"  # pass rate drops without the rule — keep
NO_EFFECT = "NO_EFFECT"            # identical pass rate — safe to delete
HARMFUL = "HARMFUL"                # pass rate RISES without the rule — delete fast

# runner returns True/False for a task verdict, or None when the trial itself
# errored (agent invocation failed) — errored trials never count as failures
TrialRunner = Callable[[str, dict], "bool | None"]


@dataclass
class AblationResult:
    rule: Rule
    with_rate: float
    without_rate: float
    trials: int
    tasks: int
    errors: int = 0  # trials that errored (excluded from both rates)

    @property
    def delta(self) -> float:
        return self.with_rate - self.without_rate

    @property
    def verdict(self) -> str:
        if self.delta > 0:
            return CARRIES_WEIGHT
        if self.delta < 0:
            return HARMFUL
        return NO_EFFECT


def strip_rule(scaffold_text: str, rule: Rule) -> str:
    """Remove one rule's source lines. `scaffold_text` must be the content of
    the file the rule was parsed from (rule.line/end_line index into it)."""
    lines = scaffold_text.splitlines()
    kept = lines[: rule.line - 1] + lines[rule.end_line :]
    return "\n".join(kept) + ("\n" if scaffold_text.endswith("\n") else "")


def _pass_rate(scaffold: str, tasks: list[dict], runner: TrialRunner, trials: int) -> "tuple[float, int]":
    runs = passes = errors = 0
    for _ in range(trials):
        for task in tasks:
            outcome = runner(scaffold, task)
            if outcome is None:
                errors += 1
                continue
            runs += 1
            passes += bool(outcome)
    return (passes / runs if runs else 0.0), errors


def ablate(
    rules: list[Rule],
    scaffold_text: str,
    tasks: list[dict],
    trial_runner: TrialRunner,
    trials: int = 3,
) -> list[AblationResult]:
    results = []
    baseline, base_errors = _pass_rate(scaffold_text, tasks, trial_runner, trials)
    for rule in rules:
        without, errors = _pass_rate(strip_rule(scaffold_text, rule), tasks, trial_runner, trials)
        results.append(
            AblationResult(rule=rule, with_rate=baseline, without_rate=without,
                           trials=trials, tasks=len(tasks), errors=base_errors + errors)
        )
    return results


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def render_ablation(results: list[AblationResult]) -> str:
    lines = ["# molt ablation report", ""]
    if results:
        n = results[0]
        rule_word = "rule" if len(results) == 1 else "rules"
        lines.append(f"{len(results)} {rule_word} × {n.tasks} tasks × {n.trials} trials each (with/without).")
        lines.append("")
    total_errors = sum(r.errors for r in results)
    if total_errors:
        lines.append(
            f"⚠ **{total_errors} trials errored** (agent invocation failed, excluded from rates). "
            f"Verdicts below rest on fewer runs than requested — treat with suspicion."
        )
        lines.append("")
    lines.append("| verdict | rule | with | without | Δ | errors |")
    lines.append("|---|---|---|---|---|---|")
    for r in sorted(results, key=lambda r: r.delta):
        lines.append(
            f"| {r.verdict} | {_cell(r.rule.short(60))} | {r.with_rate:.0%} | "
            f"{r.without_rate:.0%} | {r.delta:+.0%} | {r.errors} |"
        )
    lines.append("")
    lines.append(
        "*CARRIES_WEIGHT = keep. NO_EFFECT = safe to delete. HARMFUL = the rule "
        "actively hurts — delete fast. Small trial counts are directional, not "
        "significant; rerun with more --trials before deleting anything you fear.*"
    )
    return "\n".join(lines)
