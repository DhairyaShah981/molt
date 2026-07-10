"""v4 — prune: delete DEAD rules from scaffold files, with receipts.

The audit produces verdicts; prune acts on them. Default is a dry run that
shows exactly what would be deleted and why. --apply edits the files.
--pr wraps the edit in a branch + commit + pull request whose body carries
the evidence, so reviewers see the receipts, not just the deletions.

Only DEAD rules are pruned by default (never came up across the audited
sessions). IGNORED rules — where the situation arose and the agent didn't
comply — are included only with --include-ignored, because an ignored rule
is sometimes a rule worth *enforcing* rather than deleting. LOAD_BEARING
and UNCERTAIN are never touched.
"""

from __future__ import annotations

from pathlib import Path

from .ablate import strip_rule
from .evidence import DEAD, IGNORED, Evidence
from .rules import Rule


def select_prunable(evidences: list[Evidence], include_ignored: bool = False) -> list[Evidence]:
    wanted = {DEAD, IGNORED} if include_ignored else {DEAD}
    return [e for e in evidences if e.verdict in wanted]


def prune_texts(rules_by_file: "dict[str, list[Rule]]", texts: "dict[str, str]") -> "dict[str, str]":
    """Strip each file's condemned rules bottom-up so earlier line numbers
    stay valid while later ranges are removed."""
    out = dict(texts)
    for file, rules in rules_by_file.items():
        text = out[file]
        for rule in sorted(rules, key=lambda r: -r.line):
            text = strip_rule(text, rule)
        out[file] = text
    return out


def render_prune(prunable: list[Evidence], sessions_count: int, applied: bool = False) -> str:
    verb = "Deleted" if applied else "Would delete"
    tokens = sum(e.rule.tokens for e in prunable)
    lines = ["# molt prune", ""]
    lines.append(
        f"{verb} **{len(prunable)} rule(s)** (~{tokens} tokens/session) based on evidence "
        f"from **{sessions_count} real sessions**."
    )
    lines.append("")
    lines.append("| verdict | rule | source | tokens | discussed | acted |")
    lines.append("|---|---|---|---|---|---|")
    for e in sorted(prunable, key=lambda e: -e.rule.tokens):
        cell = e.rule.short().replace("|", "\\|")
        src = f"{Path(e.rule.file).name}:{e.rule.line}"
        lines.append(
            f"| {e.verdict} | {cell} | {src} | {e.rule.tokens} | "
            f"{e.text_hits}/{e.sessions_total} | {e.action_hits}/{e.sessions_total} |"
        )
    lines.append("")
    lines.append(
        "*Verdicts are observational lower bounds — a DEAD rule may cover a situation "
        "that simply hasn't occurred in the audited window. Review before merging.*"
    )
    return "\n".join(lines)
