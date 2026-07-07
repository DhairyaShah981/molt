"""Match rules against sessions and classify each rule.

Verdicts:
  DEAD          — rule's subject never came up across the audited sessions.
  IGNORED       — subject came up, agent did the opposite (or never complied).
  LOAD_BEARING  — evidence the rule is actively steering behavior.
  UNCERTAIN     — mixed evidence; candidate for a targeted ablation (v2).

The classifier is deliberately observational: it never runs the model, it
only greps what already happened. That makes it free, fast, and honest
about being a *lower bound* on rule usefulness.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from functools import lru_cache

from .rules import Rule
from .transcripts import Session

DEAD = "DEAD"
IGNORED = "IGNORED"
LOAD_BEARING = "LOAD_BEARING"
UNCERTAIN = "UNCERTAIN"


@dataclass
class Evidence:
    rule: Rule
    verdict: str = DEAD
    sessions_total: int = 0
    text_hits: int = 0       # subject discussed (user or assistant text)
    action_hits: int = 0     # subject appeared in commands / tool calls
    examples: list[str] = field(default_factory=list)  # session paths

    @property
    def relevant(self) -> int:
        return max(self.text_hits, self.action_hits)


@lru_cache(maxsize=4096)
def _bounded(signal: str) -> re.Pattern:
    """Word-boundary regex for a signal, so `rg` doesn't match inside `merge`.
    Multiword signals (contain a space) match as literal phrases."""
    return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(signal) + r"(?![A-Za-z0-9_])", re.I)


def _match_action(signal: str, session: Session) -> bool:
    sig = signal.lower()
    if "*" in sig:
        return any(fnmatch.fnmatch(t.lower(), sig) for t in session.tool_names) or any(
            fnmatch.fnmatch(word, sig)
            for cmd in session.bash_commands
            for word in cmd.lower().split()
        )
    pat = _bounded(signal)
    return any(pat.search(cmd) for cmd in session.bash_commands) or any(
        pat.search(t) for t in session.tool_names
    )


def _match_text(signal: str, session: Session) -> bool:
    if "*" in signal:
        # glob signals ("mcp__foo__*") reduce to prefix substring in text
        return signal.lower().replace("*", "") in session.haystack
    return bool(_bounded(signal).search(session.haystack))


def score_rule(rule: Rule, sessions: list[Session], max_examples: int = 3) -> Evidence:
    ev = Evidence(rule=rule, sessions_total=len(sessions))
    text_only = 0
    for s in sessions:
        action = any(_match_action(sig, s) for sig in rule.signals)
        text = action or any(_match_text(sig, s) for sig in rule.signals)
        if action:
            ev.action_hits += 1
        if text:
            ev.text_hits += 1
            if len(ev.examples) < max_examples:
                ev.examples.append(s.path)
        if text and not action:
            text_only += 1

    if ev.text_hits == 0 and ev.action_hits == 0:
        ev.verdict = DEAD
    elif rule.polarity == "prohibition":
        # doing the forbidden thing in commands/tools = the rule is ignored;
        # topic discussed but never acted on = the rule is holding.
        ev.verdict = IGNORED if ev.action_hits > 0 else LOAD_BEARING
    elif rule.polarity == "mandate":
        if ev.action_hits > 0 and ev.action_hits >= text_only:
            ev.verdict = LOAD_BEARING
        elif ev.action_hits > 0:
            ev.verdict = UNCERTAIN  # complied sometimes, skipped more often
        else:
            ev.verdict = IGNORED  # subject arose, mandated action never ran
    else:
        ev.verdict = LOAD_BEARING
    return ev


def audit(rules: list[Rule], sessions: list[Session]) -> list[Evidence]:
    return [score_rule(r, sessions) for r in rules]


def summarize(evidences: list[Evidence]) -> dict:
    total_tokens = sum(e.rule.tokens for e in evidences)
    by_verdict: dict[str, list[Evidence]] = {}
    for e in evidences:
        by_verdict.setdefault(e.verdict, []).append(e)
    prunable = by_verdict.get(DEAD, []) + by_verdict.get(IGNORED, [])
    return {
        "rules": len(evidences),
        "tokens": total_tokens,
        "prunable_rules": len(prunable),
        "prunable_tokens": sum(e.rule.tokens for e in prunable),
        "by_verdict": {k: len(v) for k, v in sorted(by_verdict.items())},
    }
