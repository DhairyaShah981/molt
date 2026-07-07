"""TDD tests for v2: targeted ablation (`molt ablate`).

The ablation engine must be model-agnostic: it takes a trial_runner
callback (scaffold_text, task) -> bool so tests inject a deterministic
fake and the CLI injects the real `claude -p` runner.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from molt.ablate import CARRIES_WEIGHT, HARMFUL, NO_EFFECT, ablate, strip_rule  # noqa: E402
from molt.rules import parse_all  # noqa: E402

FIXTURE = Path(__file__).resolve().parents[1] / "evals" / "fixtures" / "ablate_rules.md"

TASKS = [
    {"id": "finish", "prompt": "finish the job"},
    {"id": "style", "prompt": "format the file"},
]


def _fake_runner(scaffold: str, task: dict) -> bool:
    """Deterministic world: the 'finish' task only succeeds when the DONE.txt
    rule is present in the scaffold. The 'style' task always succeeds."""
    if task["id"] == "finish":
        return "DONE.txt" in scaffold
    return True


def test_strip_rule_removes_only_that_rule():
    rules = parse_all([FIXTURE])
    scaffold = FIXTURE.read_text()
    done_rule = next(r for r in rules if "DONE.txt" in r.text)
    stripped = strip_rule(scaffold, done_rule)
    assert "DONE.txt" not in stripped
    assert "tabs" in stripped  # the other rule survives
    assert stripped != scaffold


def test_ablate_detects_load_bearing_rule():
    rules = parse_all([FIXTURE])
    done_rule = next(r for r in rules if "DONE.txt" in r.text)
    results = ablate([done_rule], FIXTURE.read_text(), TASKS, _fake_runner, trials=2)
    assert len(results) == 1
    r = results[0]
    assert r.verdict == CARRIES_WEIGHT
    assert r.with_rate == 1.0 and r.without_rate == 0.5  # style passes, finish fails


def test_ablate_detects_no_effect_rule():
    rules = parse_all([FIXTURE])
    tabs_rule = next(r for r in rules if "tabs" in r.text)
    results = ablate([tabs_rule], FIXTURE.read_text(), TASKS, _fake_runner, trials=2)
    assert results[0].verdict == NO_EFFECT


def test_ablate_detects_harmful_rule():
    rules = parse_all([FIXTURE])
    tabs_rule = next(r for r in rules if "tabs" in r.text)

    def spiteful_runner(scaffold: str, task: dict) -> bool:
        return "tabs" not in scaffold  # everything fails while the rule exists

    results = ablate([tabs_rule], FIXTURE.read_text(), TASKS, spiteful_runner, trials=1)
    assert results[0].verdict == HARMFUL


if __name__ == "__main__":
    for k, fn in sorted(globals().items()):
        if k.startswith("test_"):
            fn()
            print(f"  ✓ {k}")
    print("\nablate tests passed")
