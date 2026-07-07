"""Render an audit into a human-readable markdown report, or machine JSON."""

from __future__ import annotations

import json
from pathlib import Path

from .evidence import DEAD, Evidence, IGNORED, LOAD_BEARING, UNCERTAIN, summarize


def _n(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def to_json(evidences: list[Evidence], sessions_count: int, file_tokens: int = 0) -> str:
    return json.dumps(
        {
            "meta": {"molt_report": 1, "sessions": sessions_count, "file_tokens": file_tokens},
            "rules": [
                {
                    "id": e.rule.id,
                    "text": e.rule.text,
                    "file": e.rule.file,
                    "line": e.rule.line,
                    "tokens": e.rule.tokens,
                    "polarity": e.rule.polarity,
                    "verdict": e.verdict,
                    "text_hits": e.text_hits,
                    "action_hits": e.action_hits,
                }
                for e in evidences
            ],
        },
        indent=2,
    )

EMOJI = {DEAD: "💀", IGNORED: "🙈", LOAD_BEARING: "🏗️", UNCERTAIN: "❓"}
ORDER = [DEAD, IGNORED, UNCERTAIN, LOAD_BEARING]

VERDICT_BLURB = {
    DEAD: "never came up in any audited session — costing tokens every session for nothing",
    IGNORED: "the situation arose and the agent did not comply — the rule isn't steering anything",
    UNCERTAIN: "mixed evidence — good candidates for a targeted ablation (or rerun with --judge)",
    LOAD_BEARING: "actively steering behavior — keep",
}


def render(evidences: list[Evidence], sessions_count: int, file_tokens: int = 0) -> str:
    s = summarize(evidences)
    lines: list[str] = []
    lines.append("# molt audit report")
    lines.append("")
    cost = f" Your scaffold files cost ~{file_tokens} tokens every session." if file_tokens else ""
    lines.append(
        f"Audited **{_n(s['rules'], 'rule')}** (~{s['tokens']} tokens of auditable rules) "
        f"against **{_n(sessions_count, 'real session')}**.{cost}"
    )
    lines.append("")
    lines.append(
        f"**Prunable: {_n(s['prunable_rules'], 'rule')} (~{s['prunable_tokens']} tokens, "
        f"{(100 * s['prunable_tokens'] // max(1, s['tokens']))}% of your scaffold).**"
    )
    lines.append("")
    lines.append("| verdict | rules |")
    lines.append("|---|---|")
    for v in ORDER:
        if s["by_verdict"].get(v):
            lines.append(f"| {EMOJI[v]} {v} | {s['by_verdict'][v]} |")
    lines.append("")

    for v in ORDER:
        group = [e for e in evidences if e.verdict == v]
        if not group:
            continue
        lines.append(f"## {EMOJI[v]} {v} — {VERDICT_BLURB[v]}")
        lines.append("")
        lines.append("| rule | source | tokens | discussed | acted |")
        lines.append("|---|---|---|---|---|")
        for e in sorted(group, key=lambda e: -e.rule.tokens):
            src = f"{Path(e.rule.file).name}:{e.rule.line}"
            cell = e.rule.short().replace("|", "\\|")
            lines.append(
                f"| {cell} | {src} | {e.rule.tokens} | "
                f"{e.text_hits}/{e.sessions_total} | {e.action_hits}/{e.sessions_total} |"
            )
        lines.append("")

    lines.append("---")
    lines.append(
        "*Verdicts are observational lower bounds mined from transcripts — a DEAD rule "
        "might matter for a situation that simply hasn't occurred yet. Delete with "
        "judgment; molt brings the evidence, you bring the call.*"
    )
    lines.append("")
    return "\n".join(lines)
