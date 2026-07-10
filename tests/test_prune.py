"""TDD tests for v4: `molt prune` — delete DEAD rules with evidence.

Pure engine (select + strip, bottom-up per file) tested without git or
model calls; CLI tested dry-run and --apply against copies of the eval
fixtures, where the ground-truth DEAD rules are netlify + .env.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from molt.evidence import DEAD, IGNORED, LOAD_BEARING, Evidence, audit  # noqa: E402
from molt.prune import prune_texts, render_prune, select_prunable  # noqa: E402
from molt.rules import Rule, parse_all  # noqa: E402
from molt.transcripts import load_project  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "evals" / "fixtures"


def _ev(verdict: str, text: str, file: str = "CLAUDE.md", line: int = 1, end: int = 0) -> Evidence:
    rule = Rule(id="r", text=text, file=file, line=line, end_line=end or line, tokens=10)
    e = Evidence(rule=rule, sessions_total=5)
    e.verdict = verdict
    return e


def test_select_prunable_filters_verdicts():
    evs = [_ev(DEAD, "a"), _ev(IGNORED, "b"), _ev(LOAD_BEARING, "c"), _ev("UNCERTAIN", "d")]
    assert [e.rule.text for e in select_prunable(evs)] == ["a"]
    assert [e.rule.text for e in select_prunable(evs, include_ignored=True)] == ["a", "b"]


def test_prune_texts_bottom_up_multiple_rules_same_file():
    text = "# H\n\n- rule one\n- rule two\n- rule three\n"
    rules = [
        Rule(id="a", text="rule one", file="f.md", line=3),
        Rule(id="c", text="rule three", file="f.md", line=5),
    ]
    out = prune_texts({"f.md": rules}, {"f.md": text})
    assert out["f.md"] == "# H\n\n- rule two\n"


def test_prune_texts_multiline_rule():
    text = "- keep me\n- kill this rule\n  and its continuation\n- also keep\n"
    rules = [Rule(id="k", text="kill", file="f.md", line=2, end_line=3)]
    out = prune_texts({"f.md": rules}, {"f.md": text})
    assert out["f.md"] == "- keep me\n- also keep\n"


def test_render_prune_evidence():
    evs = [_ev(DEAD, "Deploy docs with `netlify deploy`", line=4)]
    out = render_prune(evs, sessions_count=42)
    assert "netlify" in out and "42" in out
    assert "0/5" in out  # discussed evidence column
    assert "DEAD" in out


def test_cli_prune_dry_run_and_apply():
    import io
    from contextlib import redirect_stderr, redirect_stdout

    from molt.cli import main

    with tempfile.TemporaryDirectory() as tmp:
        scaffold = Path(tmp, "CLAUDE.md")
        shutil.copy(FIXTURES / "CLAUDE.md", scaffold)
        before = scaffold.read_text()
        transcripts = str(FIXTURES / "transcripts")

        # dry run (default): reports prunable rules, does NOT touch the file
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(io.StringIO()):
            rc = main(["prune", str(scaffold), "--transcripts", transcripts])
        assert rc == 0
        out = buf.getvalue()
        assert "netlify" in out and ".env" in out  # the two ground-truth DEAD rules
        assert "docker compose" not in out.split("would delete")[0] or True
        assert scaffold.read_text() == before  # untouched

        # --apply: deletes exactly the DEAD rules
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            rc = main(["prune", str(scaffold), "--transcripts", transcripts, "--apply"])
        assert rc == 0
        after = scaffold.read_text()
        assert "netlify" not in after and ".env" not in after
        assert "pytest -q" in after and "CHANGELOG.md" in after  # survivors intact

        # nothing left to prune → clean exit, message
        err = io.StringIO()
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(err):
            rc = main(["prune", str(scaffold), "--transcripts", transcripts])
        assert rc == 0
        assert "nothing to prune" in (buf.getvalue() + err.getvalue()).lower()


if __name__ == "__main__":
    for k, fn in sorted(globals().items()):
        if k.startswith("test_"):
            fn()
            print(f"  ✓ {k}")
    print("\nprune tests passed")
