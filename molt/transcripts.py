"""Load Claude Code session transcripts (~/.claude/projects/<slug>/*.jsonl)
into a flat, greppable Session structure.

We only need three views per session: what the user asked, what the
assistant said, and what commands/tools actually ran. Everything else in
the JSONL (attachments, snapshots, queue ops) is noise for auditing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PROJECTS_DIR = Path.home() / ".claude" / "projects"


@dataclass
class Session:
    path: str
    user_text: str = ""
    assistant_text: str = ""
    bash_commands: list[str] = field(default_factory=list)
    tool_names: list[str] = field(default_factory=list)
    n_messages: int = 0

    @property
    def haystack(self) -> str:
        """Everything searchable, lowercased, built once."""
        if not hasattr(self, "_haystack"):
            self._haystack = "\n".join(
                [self.user_text, self.assistant_text, "\n".join(self.bash_commands), "\n".join(self.tool_names)]
            ).lower()
        return self._haystack


def project_slug(cwd: Path) -> str:
    """Claude Code names a project dir by replacing path separators and dots
    with dashes: /Users/me/my.app -> -Users-me-my-app"""
    return str(cwd.resolve()).replace("/", "-").replace(".", "-").replace("_", "-")


def _blocks(content) -> list[dict]:
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return []


def load_session(path: Path, max_bytes: int = 50_000_000) -> Session | None:
    if path.stat().st_size > max_bytes:
        return None  # pathological log; skip rather than stall
    s = Session(path=str(path))
    texts_user: list[str] = []
    texts_asst: list[str] = []
    try:
        with path.open(errors="replace") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = d.get("type")
                if t not in ("user", "assistant"):
                    continue
                msg = d.get("message") or {}
                s.n_messages += 1
                for b in _blocks(msg.get("content")):
                    bt = b.get("type")
                    if bt == "text":
                        (texts_user if t == "user" else texts_asst).append(b.get("text") or "")
                    elif bt == "tool_use":
                        name = b.get("name") or ""
                        s.tool_names.append(name)
                        inp = b.get("input") or {}
                        if name.lower() == "bash" and isinstance(inp.get("command"), str):
                            s.bash_commands.append(inp["command"])
    except OSError:
        return None
    if s.n_messages == 0:
        return None
    s.user_text = "\n".join(texts_user)
    s.assistant_text = "\n".join(texts_asst)
    return s


def load_project(project_dir: Path, limit: int = 0) -> list[Session]:
    files = sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if limit:
        files = files[:limit]
    sessions = []
    for f in files:
        s = load_session(f)
        if s:
            sessions.append(s)
    return sessions


def discover(cwd: Path | None = None, all_projects: bool = False, limit: int = 0,
             projects_dir: Path = DEFAULT_PROJECTS_DIR) -> list[Session]:
    if not projects_dir.is_dir():
        return []
    if all_projects:
        sessions: list[Session] = []
        for d in sorted(projects_dir.iterdir()):
            if d.is_dir():
                sessions.extend(load_project(d, limit=0))
        # apply limit globally, newest first
        sessions.sort(key=lambda s: Path(s.path).stat().st_mtime, reverse=True)
        return sessions[:limit] if limit else sessions
    slug = project_slug(cwd or Path.cwd())
    d = projects_dir / slug
    return load_project(d, limit=limit) if d.is_dir() else []
