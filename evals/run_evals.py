#!/usr/bin/env python3
"""Eval harness for molt's classifier.

Fixtures are synthetic sessions with hand-labeled ground truth covering
every verdict class. The classifier must score 100% on them — they are
regression contracts, not a benchmark to climb.

Usage: python evals/run_evals.py
Exit code 0 = all verdicts match ground truth.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from molt.diffcmd import diff_reports  # noqa: E402
from molt.evidence import audit  # noqa: E402
from molt.report import to_json  # noqa: E402
from molt.rules import parse_all  # noqa: E402
from molt.transcripts import load_project, load_session  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"

# Capability-diff contract: era-old = sessions s1+s2, era-new = s3.
# Every expected transition is hand-derived from the fixtures.
EXPECTED_TRANSITIONS = {
    ("pip install", "IGNORED", "DEAD"),
    ("pytest -q", "LOAD_BEARING", "DEAD"),
    ("instead of `grep`", "LOAD_BEARING", "DEAD"),
    ("docker compose", "DEAD", "IGNORED"),
    ("CHANGELOG.md", "IGNORED", "LOAD_BEARING"),
}
EXPECTED_UNCHANGED = 2  # netlify + .env stay DEAD in both eras


def eval_diff() -> int:
    rules = parse_all([FIXTURES / "CLAUDE.md"])
    old_sessions = [load_session(FIXTURES / "transcripts" / f) for f in ("s1.jsonl", "s2.jsonl")]
    new_sessions = [load_session(FIXTURES / "transcripts" / "s3.jsonl")]
    old = json.loads(to_json(audit(rules, old_sessions), len(old_sessions)))
    new = json.loads(to_json(audit(rules, new_sessions), len(new_sessions)))
    d = diff_reports(old, new)

    failed = 0
    got = {(t["from"], t["to"], t["text"]) for t in d["transitions"]}
    for key, frm, to in EXPECTED_TRANSITIONS:
        hit = any(key in text and (f, t) == (frm, to) for f, t, text in got)
        print(f"  {'✓' if hit else '✗'} diff: {key!r} {frm} → {to}")
        failed += not hit
    if len(d["transitions"]) != len(EXPECTED_TRANSITIONS):
        print(f"  ✗ diff: expected {len(EXPECTED_TRANSITIONS)} transitions, got {len(d['transitions'])}")
        failed += 1
    if d["unchanged"] != EXPECTED_UNCHANGED:
        print(f"  ✗ diff: expected {EXPECTED_UNCHANGED} unchanged, got {d['unchanged']}")
        failed += 1
    return failed


def main() -> int:
    labels: dict[str, str] = {
        k: v for k, v in json.loads((Path(__file__).parent / "labels.json").read_text()).items()
        if not k.startswith("_")
    }
    rules = parse_all([FIXTURES / "CLAUDE.md"])
    sessions = load_project(FIXTURES / "transcripts", limit=0)
    assert sessions, "fixture transcripts failed to load"
    evidences = audit(rules, sessions)

    passed = failed = 0
    matched_keys: set[str] = set()
    for ev in evidences:
        expected = None
        for key, verdict in labels.items():
            if key in ev.rule.text:
                expected, matched_keys = verdict, matched_keys | {key}
                break
        if expected is None:
            print(f"  ⚠ unlabeled rule (add to labels.json): {ev.rule.short()}")
            continue
        ok = ev.verdict == expected
        passed += ok
        failed += not ok
        mark = "✓" if ok else "✗"
        detail = "" if ok else f"  (expected {expected}, got {ev.verdict}; text={ev.text_hits} action={ev.action_hits})"
        print(f"  {mark} [{ev.verdict:12s}] {ev.rule.short(60)}{detail}")

    for key in set(labels) - matched_keys:
        print(f"  ✗ label never matched any parsed rule: {key!r}")
        failed += 1

    print()
    failed += eval_diff()

    total = passed + failed
    print(f"\nclassifier: {passed}/{total} · diff contract: {'PASS' if failed == 0 else 'FAIL'}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
