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


def test_strip_rule_multiline_rule():
    import tempfile

    body = (
        "# Rules\n"
        "\n"
        "- Always create `DONE.txt` when finished\n"
        "  and verify it exists afterwards.\n"
        "- Never use tabs for indentation.\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
        fh.write(body)
        tmp = Path(fh.name)
    try:
        rules = parse_all([tmp])
        done = next(r for r in rules if "DONE.txt" in r.text)
        assert done.end_line == done.line + 1  # continuation line tracked
        stripped = strip_rule(body, done)
        assert "DONE.txt" not in stripped and "verify it exists" not in stripped
        assert "tabs" in stripped
        assert stripped.endswith("\n")  # trailing newline preserved
        # no trailing newline in source -> none in output
        assert not strip_rule(body.rstrip("\n"), done).endswith("\n")
    finally:
        tmp.unlink()


def test_render_ablation_report():
    from molt.ablate import render_ablation

    rules = parse_all([FIXTURE])
    results = ablate(rules, FIXTURE.read_text(), TASKS, _fake_runner, trials=1)
    out = render_ablation(results)
    assert "2 rules × 2 tasks × 1 trials" in out
    assert CARRIES_WEIGHT in out and NO_EFFECT in out
    # sorted by delta ascending: NO_EFFECT (0) row precedes CARRIES_WEIGHT (+50%)
    assert out.index(NO_EFFECT) < out.index(CARRIES_WEIGHT)
    assert "+50%" in out
    # empty results: still a valid report, no crash, no per-run header line
    empty = render_ablation([])
    assert "# molt ablation report" in empty and "rules ×" not in empty


def test_ablate_empty_tasks_rates_zero():
    rules = parse_all([FIXTURE])
    results = ablate(rules[:1], FIXTURE.read_text(), [], _fake_runner, trials=2)
    r = results[0]
    assert r.with_rate == 0.0 and r.without_rate == 0.0  # runs == 0 guard
    assert r.verdict == NO_EFFECT


def test_ablate_errored_trials_excluded():
    from molt.ablate import render_ablation

    rules = parse_all([FIXTURE])
    tabs_rule = next(r for r in rules if "tabs" in r.text)

    def flaky_runner(scaffold: str, task: dict):
        if task["id"] == "finish":
            return None  # agent invocation failed — not a task verdict
        return True

    results = ablate([tabs_rule], FIXTURE.read_text(), TASKS, flaky_runner, trials=2)
    r = results[0]
    assert r.errors == 4  # (baseline + without) x 2 trials x 1 erroring task
    assert r.with_rate == 1.0 and r.without_rate == 1.0  # style-only denominator
    assert "trials errored" in render_ablation(results)


def test_cli_ablate_input_validation():
    import io
    import json
    import shutil
    import tempfile
    from contextlib import redirect_stderr, redirect_stdout

    from molt.cli import main

    real_which = shutil.which
    shutil.which = lambda cmd, *a, **kw: "/usr/bin/claude" if cmd == "claude" else real_which(cmd, *a, **kw)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            scaffold = Path(tmp, "CLAUDE.md")
            scaffold.write_text("- Always run `pytest` before committing.\n")
            # empty tasks list rejected (would yield universal NO_EFFECT from zero data)
            empty = Path(tmp, "empty.json")
            empty.write_text("[]")
            err = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(err):
                rc = main(["ablate", str(scaffold), "--tasks", str(empty)])
            assert rc == 1 and "non-empty JSON list" in err.getvalue()
            # entry missing "check" rejected
            bad = Path(tmp, "bad.json")
            bad.write_text(json.dumps([{"prompt": "do it"}]))
            err = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(err):
                rc = main(["ablate", str(scaffold), "--tasks", str(bad)])
            assert rc == 1 and "non-empty JSON list" in err.getvalue()
            # global CLAUDE.md refused (claude -p loads it in both trial arms)
            global_md = Path.home() / ".claude" / "CLAUDE.md"
            if global_md.is_file():
                tasks = Path(tmp, "t.json")
                tasks.write_text(json.dumps([{"prompt": "x", "check": "true"}]))
                err = io.StringIO()
                with redirect_stdout(io.StringIO()), redirect_stderr(err):
                    rc = main(["ablate", str(global_md), "--tasks", str(tasks)])
                assert rc == 1 and "cannot ablate the global" in err.getvalue()
    finally:
        shutil.which = real_which


if __name__ == "__main__":
    for k, fn in sorted(globals().items()):
        if k.startswith("test_"):
            fn()
            print(f"  ✓ {k}")
    print("\nablate tests passed")
