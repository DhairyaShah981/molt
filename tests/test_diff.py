"""TDD tests for v3: capability diff (`molt audit --json` + `molt diff`).

Run the same scaffold against two transcript eras (old model vs new
model), diff the verdicts, and read off what the new model internalized.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from molt.diffcmd import diff_reports, render_diff  # noqa: E402
from molt.evidence import audit  # noqa: E402
from molt.report import to_json  # noqa: E402
from molt.rules import parse_all  # noqa: E402
from molt.transcripts import Session, filter_by_date  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "evals" / "fixtures"


def _report(verdicts: dict[str, str]) -> dict:
    return {
        "meta": {"sessions": 10},
        "rules": [
            {"text": t, "verdict": v, "tokens": 10, "file": "CLAUDE.md", "line": i}
            for i, (t, v) in enumerate(verdicts.items(), 1)
        ],
    }


def test_diff_reports_transitions():
    old = _report({"Always run tests": "IGNORED", "Never push to main": "LOAD_BEARING", "Use rg": "DEAD"})
    new = _report({"Always run tests": "LOAD_BEARING", "Never push to main": "DEAD", "Use rg": "DEAD"})
    d = diff_reports(old, new)
    transitions = {(t["text"], t["from"], t["to"]) for t in d["transitions"]}
    assert ("Always run tests", "IGNORED", "LOAD_BEARING") in transitions
    assert ("Never push to main", "LOAD_BEARING", "DEAD") in transitions
    assert d["unchanged"] == 1


def test_diff_handles_added_and_removed_rules():
    old = _report({"Rule A": "DEAD"})
    new = _report({"Rule B": "DEAD"})
    d = diff_reports(old, new)
    assert d["removed"] == ["Rule A"]
    assert d["added"] == ["Rule B"]


def test_render_diff_interprets_internalization():
    old = _report({"Never push to main": "LOAD_BEARING"})
    new = _report({"Never push to main": "DEAD"})
    out = render_diff(diff_reports(old, new))
    assert "Never push to main" in out
    assert "internalized" in out.lower() or "obsolete" in out.lower()


def test_audit_to_json_roundtrip():
    rules = parse_all([FIXTURES / "CLAUDE.md"])
    sessions = [Session(path="s1", user_text="run pytest -q please", bash_commands=["pytest -q"])]
    evidences = audit(rules, sessions)
    blob = json.loads(to_json(evidences, sessions_count=1, file_tokens=88))
    assert blob["meta"]["sessions"] == 1
    assert blob["meta"]["file_tokens"] == 88
    assert len(blob["rules"]) == len(rules)
    assert all({"text", "verdict", "tokens", "file", "line"} <= set(r) for r in blob["rules"])


def test_filter_by_date():
    s1 = Session(path="a", started="2026-01-15T10:00:00Z")
    s2 = Session(path="b", started="2026-06-20T10:00:00Z")
    s3 = Session(path="c", started="")  # unknown date: kept only when no bounds
    assert filter_by_date([s1, s2, s3], since="2026-03-01", until="") == [s2]
    assert filter_by_date([s1, s2, s3], since="", until="2026-03-01") == [s1]
    assert filter_by_date([s1, s2, s3], since="", until="") == [s1, s2, s3]


if __name__ == "__main__":
    for k, fn in sorted(globals().items()):
        if k.startswith("test_"):
            fn()
            print(f"  ✓ {k}")
    print("\ndiff tests passed")
