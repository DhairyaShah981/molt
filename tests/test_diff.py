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


def test_render_diff_edge_cases():
    # missing meta -> session counts default to 0; missing tokens -> 0
    old = _report({"Rule A": "IGNORED", "Gone": "DEAD"})
    new = {"rules": [{"text": "Rule A", "verdict": "DEAD"}, {"text": "Fresh", "verdict": "DEAD"}]}
    d = diff_reports(old, new)
    assert d["old_sessions"] == 10 and d["new_sessions"] == 0
    assert d["transitions"][0]["tokens"] == 0  # tokens read from new report, defaulted
    assert d["removed"] == ["Gone"] and d["added"] == ["Fresh"]
    out = render_diff(d)
    assert "Rules removed since old report" in out and "Gone" in out
    assert "Rules added since old report" in out and "Fresh" in out
    # unknown verdict pair falls back to the generic reading
    weird = diff_reports(_report({"X rule here": "BOGUS"}), _report({"X rule here": "DEAD"}))
    assert weird["transitions"][0]["why"] == "verdict changed"
    # long rule text is truncated to 64 chars with ellipsis
    long_text = "Always " + "x" * 80
    out2 = render_diff(diff_reports(_report({long_text: "IGNORED"}), _report({long_text: "DEAD"})))
    assert long_text[:63] + "…" in out2 and long_text not in out2
    # no transitions at all -> no table, header still sane
    out3 = render_diff(diff_reports(_report({"Same": "DEAD"}), _report({"Same": "DEAD"})))
    assert "0 verdicts changed, 1 unchanged" in out3 and "| rule |" not in out3


def test_load_session_started_and_both_bounds():
    import tempfile

    from molt.transcripts import load_session

    lines = (
        '{"type": "summary", "timestamp": "2026-05-01T09:00:00Z"}\n'
        '{"type": "user", "timestamp": "2026-05-01T09:05:00Z", '
        '"message": {"role": "user", "content": "run the tests"}}\n'
    )
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
        fh.write(lines)
        tmp = Path(fh.name)
    try:
        s = load_session(tmp)
        assert s is not None
        assert s.started == "2026-05-01T09:00:00Z"  # first timestamp wins
        assert filter_by_date([s], since="2026-04-01", until="2026-06-01") == [s]
        assert filter_by_date([s], since="2026-05-02", until="2026-06-01") == []
        assert filter_by_date([s], since="2026-04-01", until="2026-05-01") == []  # until is exclusive
    finally:
        tmp.unlink()


def test_cli_diff_command():
    import contextlib
    import io
    import tempfile

    from molt.cli import main

    old = _report({"Never push to main": "LOAD_BEARING"})
    new = _report({"Never push to main": "DEAD"})
    with tempfile.TemporaryDirectory() as tmp:
        old_p, new_p = Path(tmp, "old.json"), Path(tmp, "new.json")
        old_p.write_text(json.dumps(old))
        new_p.write_text(json.dumps(new))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(["diff", str(old_p), str(new_p)])
    assert rc == 0
    out = buf.getvalue()
    assert "molt capability diff" in out
    assert "LOAD_BEARING → DEAD" in out and "Never push to main" in out


def test_cli_audit_json_and_date_filter():
    import contextlib
    import io

    from molt.cli import main

    scaffold = str(FIXTURES / "CLAUDE.md")
    transcripts = str(FIXTURES / "transcripts")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["audit", scaffold, "--transcripts", transcripts, "--json"])
    assert rc == 0
    blob = json.loads(buf.getvalue())
    assert blob["meta"]["sessions"] == 3
    assert {r["verdict"] for r in blob["rules"]} <= {"DEAD", "IGNORED", "UNCERTAIN", "LOAD_BEARING"}
    # fixture transcripts carry no timestamps -> any --since bound empties the set
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        rc = main(["audit", scaffold, "--transcripts", transcripts, "--since", "2020-01-01"])
    assert rc == 1
    assert "no sessions left" in err.getvalue()


if __name__ == "__main__":
    for k, fn in sorted(globals().items()):
        if k.startswith("test_"):
            fn()
            print(f"  ✓ {k}")
    print("\ndiff tests passed")
