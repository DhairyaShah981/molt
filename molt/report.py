"""Render an audit into a human-readable markdown report."""

from __future__ import annotations

from pathlib import Path

from .evidence import DEAD, Evidence, IGNORED, LOAD_BEARING, UNCERTAIN, summarize

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
        f"Audited **{s['rules']} rules** (~{s['tokens']} tokens of auditable rules) "
        f"against **{sessions_count} real sessions**.{cost}"
    )
    lines.append("")
    lines.append(
        f"**Prunable: {s['prunable_rules']} rules (~{s['prunable_tokens']} tokens, "
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
            lines.append(
                f"| {e.rule.short()} | {src} | {e.rule.tokens} | "
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
