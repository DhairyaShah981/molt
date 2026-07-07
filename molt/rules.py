"""Parse CLAUDE.md-style instruction files into individual auditable rules.

A "rule" is the atomic unit molt reasons about: one bullet point or one
imperative paragraph. Each rule carries its provenance (file:line), an
estimated token cost, extracted signal terms (backtick spans beat prose),
and a polarity (prohibition / mandate / info).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)")
BACKTICK_RE = re.compile(r"`([^`]+)`")
IMPORT_RE = re.compile(r"^@(\S+)\s*$", re.MULTILINE)
PROHIBITION_RE = re.compile(r"\b(never|don'?t|do not|avoid|no longer|forbidden|refuse)\b", re.I)
MANDATE_RE = re.compile(r"\b(always|must|use|prefer|ensure|require[ds]?|only use)\b", re.I)

STOPWORDS = frozenset(
    "the a an and or of to in for with is are be this that it its from on at by as "
    "you your all any not when if then than into out over under will can may should "
    "would could there here what which who how why do does did done have has had "
    "was were been being them they we our us i me my these those also more most "
    "some such very just like via per each other after before".split()
)


@dataclass
class Rule:
    id: str
    text: str
    file: str
    line: int
    heading: str = ""
    tokens: int = 0
    polarity: str = "info"  # prohibition | mandate | info
    signals: list[str] = field(default_factory=list)

    def short(self, width: int = 72) -> str:
        t = " ".join(self.text.split())
        return t if len(t) <= width else t[: width - 1] + "…"


def _estimate_tokens(text: str) -> int:
    # ponytail: chars/4 heuristic, good enough for ranking. Swap for a real
    # tokenizer if per-token billing accuracy ever matters.
    return max(1, len(text) // 4)


def _polarity(text: str) -> str:
    if PROHIBITION_RE.search(text):
        return "prohibition"
    if MANDATE_RE.search(text):
        return "mandate"
    return "info"


def _signals(text: str) -> list[str]:
    """Terms we can actually grep transcripts for. Backtick spans are gold
    (commands, tool names, paths); fall back to rare content words."""
    ticks = [t.strip() for t in BACKTICK_RE.findall(text) if len(t.strip()) >= 2]
    if ticks:
        return ticks[:6]
    words = re.findall(r"[A-Za-z][A-Za-z0-9_/.-]{3,}", text)
    content = [w for w in words if w.lower() not in STOPWORDS]
    # longest words are usually the most identifying (tool names, jargon)
    content.sort(key=len, reverse=True)
    seen: list[str] = []
    for w in content:
        if w.lower() not in {s.lower() for s in seen}:
            seen.append(w)
        if len(seen) == 4:
            break
    return seen


def _slug(text: str, n: int) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())[:5]
    return f"r{n:03d}-" + "-".join(words)[:48]


def resolve_imports(path: Path, seen: set[Path] | None = None) -> list[Path]:
    """CLAUDE.md supports `@file.md` include lines. Resolve one file into the
    ordered list of files it pulls in (depth-first, cycle-safe)."""
    seen = seen if seen is not None else set()
    path = path.resolve()
    if path in seen or not path.is_file():
        return []
    seen.add(path)
    out = [path]
    try:
        body = path.read_text(errors="replace")
    except OSError:
        return out
    for m in IMPORT_RE.finditer(body):
        target = m.group(1)
        candidate = (path.parent / target).resolve()
        if not candidate.is_file() and not target.endswith(".md"):
            candidate = (path.parent / f"{target}.md").resolve()
        out.extend(resolve_imports(candidate, seen))
    return out


def parse_file(path: Path) -> list[Rule]:
    rules: list[Rule] = []
    heading = ""
    in_fence = False
    pending: list[str] = []  # continuation lines of the current bullet
    pending_line = 0

    def flush() -> None:
        nonlocal pending
        if not pending:
            return
        text = " ".join(" ".join(pending).split())
        if len(text) >= 8:
            rules.append(
                Rule(
                    id=_slug(text, len(rules) + 1),
                    text=text,
                    file=str(path),
                    line=pending_line,
                    heading=heading,
                    tokens=_estimate_tokens(text),
                    polarity=_polarity(text),
                    signals=_signals(text),
                )
            )
        pending = []

    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return []

    for i, raw in enumerate(lines, 1):
        line = raw.rstrip()
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if line.startswith("#"):
            flush()
            heading = line.lstrip("# ").strip()
            continue
        if IMPORT_RE.match(line):
            flush()
            continue
        m = BULLET_RE.match(line)
        if m:
            flush()
            pending = [m.group(1)]
            pending_line = i
        elif pending and line.strip() and (raw.startswith((" ", "\t"))):
            pending.append(line.strip())
        else:
            flush()
            text = line.strip()
            # bare paragraphs count as rules when they command something or
            # reference concrete commands/tools (backticks = auditable)
            if text and (_polarity(text) != "info" or BACKTICK_RE.search(text)):
                rules.append(
                    Rule(
                        id=_slug(text, len(rules) + 1),
                        text=text,
                        file=str(path),
                        line=i,
                        heading=heading,
                        tokens=_estimate_tokens(text),
                        polarity=_polarity(text),
                        signals=_signals(text),
                    )
                )
    flush()
    return rules


def parse_all(paths: list[Path]) -> list[Rule]:
    rules: list[Rule] = []
    for p in expand_paths(paths):
        rules.extend(parse_file(p))
    # re-number ids globally so they stay unique across files
    for n, r in enumerate(rules, 1):
        r.id = _slug(r.text, n)
    return rules


def expand_paths(paths: list[Path]) -> list[Path]:
    expanded: list[Path] = []
    for p in paths:
        expanded.extend(resolve_imports(p))
    return list(dict.fromkeys(expanded))


def file_tokens(paths: list[Path]) -> int:
    """Total token cost of the scaffold files themselves (rules + prose +
    headings + fences) — what every session actually pays."""
    total = 0
    for p in expand_paths(paths):
        try:
            total += _estimate_tokens(p.read_text(errors="replace"))
        except OSError:
            pass
    return total
