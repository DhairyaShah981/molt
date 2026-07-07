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

from molt.evidence import audit  # noqa: E402
from molt.rules import parse_all  # noqa: E402
from molt.transcripts import load_project  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


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

    total = passed + failed
    print(f"\n{passed}/{total} verdicts correct")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
