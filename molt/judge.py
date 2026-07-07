"""Optional LLM judge for UNCERTAIN rules.

Observational grepping can't read intent. For the handful of rules the
heuristics can't settle, we ask a model to look at real session excerpts
and answer: was this rule relevant, and was it followed?

Uses the `claude` CLI in print mode so users need zero extra setup beyond
the tool whose config they are auditing. No API key handling, no SDK dep.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

from .evidence import Evidence, IGNORED, LOAD_BEARING, UNCERTAIN
from .transcripts import Session

PROMPT = """You are auditing whether an agent instruction ("rule") earns its place.

RULE: {rule}

Below are excerpts from a real agent session (user request, assistant
behavior, commands run). Answer with ONLY a JSON object:
{{"relevant": true/false, "followed": true/false, "reason": "<one line>"}}

"relevant" = a situation arose where this rule applies.
"followed" = the assistant's behavior complied with the rule.

SESSION EXCERPT:
{excerpt}
"""


def _excerpt(s: Session, budget: int = 6000) -> str:
    parts = [
        "USER:\n" + s.user_text[: budget // 3],
        "ASSISTANT:\n" + s.assistant_text[: budget // 3],
        "COMMANDS:\n" + "\n".join(s.bash_commands)[: budget // 3],
    ]
    return "\n\n".join(parts)


def judge_available() -> bool:
    return shutil.which("claude") is not None


def judge_rule(ev: Evidence, sessions: list[Session], samples: int = 3, model: str = "haiku") -> Evidence:
    """Re-verdict one UNCERTAIN rule by sampling sessions where it hit."""
    hit_paths = set(ev.examples)
    sampled = [s for s in sessions if s.path in hit_paths][:samples]
    if not sampled:
        return ev
    relevant = followed = 0
    for s in sampled:
        prompt = PROMPT.format(rule=ev.rule.text, excerpt=_excerpt(s))
        try:
            out = subprocess.run(
                ["claude", "-p", prompt, "--model", model],
                capture_output=True, text=True, timeout=120,
            ).stdout
        except (subprocess.TimeoutExpired, OSError):
            continue
        m = re.search(r"\{.*\}", out, re.S)
        if not m:
            continue
        try:
            d = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        relevant += bool(d.get("relevant"))
        followed += bool(d.get("followed"))
    if relevant == 0:
        return ev  # judge saw nothing decisive; keep UNCERTAIN
    ev.verdict = LOAD_BEARING if followed * 2 >= relevant else IGNORED
    return ev


def judge_uncertain(evidences: list[Evidence], sessions: list[Session], samples: int = 3) -> list[Evidence]:
    if not judge_available():
        raise RuntimeError("`claude` CLI not found on PATH; --judge needs it")
    return [judge_rule(e, sessions, samples) if e.verdict == UNCERTAIN else e for e in evidences]
