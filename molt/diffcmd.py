"""v3 — capability diff.

Audit the same scaffold against two transcript eras (old model vs new
model, or before/after a workflow change), then diff the verdicts. Rules
that were LOAD_BEARING and became DEAD are your capability changelog:
scaffold the new era no longer needs.

    molt audit --until 2026-06-01 --json --out old.json
    molt audit --since 2026-06-01 --json --out new.json
    molt diff old.json new.json
"""

from __future__ import annotations

INTERPRET = {
    ("LOAD_BEARING", "DEAD"): "subject stopped arising — likely internalized or obsolete",
    ("UNCERTAIN", "DEAD"): "subject stopped arising — likely internalized or obsolete",
    ("IGNORED", "DEAD"): "subject stopped arising — rule was dead weight anyway",
    ("IGNORED", "LOAD_BEARING"): "now complied with — rule started steering (or model improved)",
    ("IGNORED", "UNCERTAIN"): "compliance improving",
    ("LOAD_BEARING", "IGNORED"): "regression — compliance dropped",
    ("UNCERTAIN", "IGNORED"): "regression — compliance dropped",
    ("DEAD", "LOAD_BEARING"): "subject now arises and rule steers it",
    ("DEAD", "IGNORED"): "subject now arises and rule is being ignored",
    ("DEAD", "UNCERTAIN"): "subject now arises, evidence mixed",
    ("LOAD_BEARING", "UNCERTAIN"): "evidence weakened",
    ("UNCERTAIN", "LOAD_BEARING"): "evidence firmed up — keep",
}


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def diff_reports(old: dict, new: dict) -> dict:
    old_rules = {_norm(r["text"]): r for r in old["rules"]}
    new_rules = {_norm(r["text"]): r for r in new["rules"]}
    transitions = []
    unchanged = 0
    for key in old_rules.keys() & new_rules.keys():
        o, n = old_rules[key], new_rules[key]
        if o["verdict"] == n["verdict"]:
            unchanged += 1
        else:
            transitions.append(
                {
                    "text": n["text"],
                    "from": o["verdict"],
                    "to": n["verdict"],
                    "tokens": n.get("tokens", 0),
                    "why": INTERPRET.get((o["verdict"], n["verdict"]), "verdict changed"),
                }
            )
    return {
        "transitions": sorted(transitions, key=lambda t: -t["tokens"]),
        "unchanged": unchanged,
        "removed": sorted(old_rules[k]["text"] for k in old_rules.keys() - new_rules.keys()),
        "added": sorted(new_rules[k]["text"] for k in new_rules.keys() - old_rules.keys()),
        "old_sessions": old.get("meta", {}).get("sessions", 0),
        "new_sessions": new.get("meta", {}).get("sessions", 0),
    }


def render_diff(d: dict) -> str:
    lines = ["# molt capability diff", ""]
    lines.append(
        f"Old era: {d['old_sessions']} sessions · New era: {d['new_sessions']} sessions · "
        f"{len(d['transitions'])} verdicts changed, {d['unchanged']} unchanged."
    )
    lines.append("")
    if d["transitions"]:
        lines.append("| rule | from → to | reading |")
        lines.append("|---|---|---|")
        for t in d["transitions"]:
            short = t["text"] if len(t["text"]) <= 64 else t["text"][:63] + "…"
            short = short.replace("|", "\\|")
            lines.append(f"| {short} | {t['from']} → {t['to']} | {t['why']} |")
        lines.append("")
    internalized = [t for t in d["transitions"] if t["to"] == "DEAD" and t["from"] != "IGNORED"]
    if internalized:
        saved = sum(t["tokens"] for t in internalized)
        lines.append(
            f"**Internalization candidates: {len(internalized)} rules (~{saved} tokens) the "
            f"new era no longer exercises. Verify, then molt them.**"
        )
        lines.append("")
    for label, key in (("Rules removed since old report", "removed"), ("Rules added since old report", "added")):
        if d[key]:
            lines.append(f"*{label}:* " + "; ".join(d[key]))
            lines.append("")
    return "\n".join(lines)
