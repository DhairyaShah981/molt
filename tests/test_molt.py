"""Unit checks for molt's parsing and matching. Plain asserts, no framework.

Run: python tests/test_molt.py  (or pytest -q)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from molt.evidence import _bounded, _match_action, score_rule  # noqa: E402
from molt.rules import Rule, _polarity, _signals, parse_all  # noqa: E402
from molt.transcripts import Session, project_slug  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "evals" / "fixtures"


def test_polarity():
    assert _polarity("Never use pip directly") == "prohibition"
    assert _polarity("Always run the linter") == "mandate"
    assert _polarity("The build takes five minutes") == "info"
    # prohibition wins when both cues appear
    assert _polarity("Never use X; always use Y") == "prohibition"


def test_signals_prefer_backticks():
    assert _signals("Use `rg` instead of `grep`") == ["rg", "grep"]
    sig = _signals("Benchmark competitors before any strategy plan")
    assert sig and "the" not in sig


def test_word_boundary():
    assert not _bounded("rg").search("git merge main")
    assert _bounded("rg").search("rg TODO src/")
    assert _bounded("pip install").search("pip install requests")


def test_glob_matches_tool_names():
    s = Session(path="x", tool_names=["mcp__claude-in-chrome__screenshot"])
    r = Rule(id="r", text="never", file="f", line=1, signals=["mcp__claude-in-chrome__*"])
    assert _match_action(r.signals[0], s)


def test_parse_fixture_rules():
    rules = parse_all([FIXTURES / "CLAUDE.md"])
    assert len(rules) == 7, f"expected 7 rules, got {len(rules)}"
    assert all(r.tokens > 0 and r.signals for r in rules)


def test_score_dead_rule():
    r = Rule(id="r", text="Deploy with `netlify deploy`", file="f", line=1,
             polarity="mandate", signals=["netlify deploy"])
    ev = score_rule(r, [Session(path="s", user_text="hello", assistant_text="hi")])
    assert ev.verdict == "DEAD"


def test_project_slug():
    assert project_slug(Path("/Users/me/my.app")) == "-Users-me-my-app"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tests passed")
