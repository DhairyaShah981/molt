"""molt CLI.

  molt scan  [files...]           inventory rules + token cost (static, instant)
  molt audit [files...] [flags]   mine transcripts, classify every rule
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .evidence import audit as run_audit
from .report import render
from .rules import file_tokens, parse_all
from .transcripts import DEFAULT_PROJECTS_DIR, discover


def default_claude_mds() -> list[Path]:
    candidates = [
        Path.home() / ".claude" / "CLAUDE.md",
        Path.cwd() / "CLAUDE.md",
        Path.cwd() / ".claude" / "CLAUDE.md",
    ]
    return [p for p in candidates if p.is_file()]


def cmd_scan(args: argparse.Namespace) -> int:
    paths = [Path(p) for p in args.files] or default_claude_mds()
    if not paths:
        print("no CLAUDE.md found (looked in ~/.claude and cwd); pass paths explicitly", file=sys.stderr)
        return 1
    rules = parse_all(paths)
    total = sum(r.tokens for r in rules)
    print(f"{len(rules)} rules, ~{total} tokens\n")
    for r in rules:
        print(f"  [{r.polarity:11s}] ~{r.tokens:4d}tok  {Path(r.file).name}:{r.line:<4d} {r.short(90)}")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    paths = [Path(p) for p in args.files] or default_claude_mds()
    if not paths:
        print("no CLAUDE.md found; pass paths explicitly", file=sys.stderr)
        return 1
    rules = parse_all(paths)
    if not rules:
        print("no rules parsed from input files", file=sys.stderr)
        return 1

    projects_dir = Path(args.transcripts) if args.transcripts else DEFAULT_PROJECTS_DIR
    if args.transcripts and projects_dir.is_dir() and list(projects_dir.glob("*.jsonl")):
        # a directory of .jsonl files directly (fixtures / exported logs)
        from .transcripts import load_project

        sessions = load_project(projects_dir, limit=args.limit)
    else:
        sessions = discover(all_projects=args.all_projects, limit=args.limit, projects_dir=projects_dir)
    if not sessions:
        print(f"no transcripts found under {projects_dir}", file=sys.stderr)
        return 1

    evidences = run_audit(rules, sessions)
    if args.judge:
        from .judge import judge_uncertain

        evidences = judge_uncertain(evidences, sessions)

    out = render(evidences, len(sessions), file_tokens=file_tokens(paths))
    if args.out:
        Path(args.out).write_text(out)
        print(f"report written to {args.out}")
    else:
        print(out)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="molt", description="scaffold-debt auditor for agent instruction files")
    ap.add_argument("--version", action="version", version=f"molt {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="list rules and token cost (no transcripts needed)")
    p_scan.add_argument("files", nargs="*", help="CLAUDE.md-style files (default: auto-discover)")
    p_scan.set_defaults(fn=cmd_scan)

    p_audit = sub.add_parser("audit", help="classify every rule against real session transcripts")
    p_audit.add_argument("files", nargs="*", help="CLAUDE.md-style files (default: auto-discover)")
    p_audit.add_argument("--transcripts", help="transcripts dir (default: ~/.claude/projects, current project)")
    p_audit.add_argument("--all-projects", action="store_true", help="audit across every project's transcripts")
    p_audit.add_argument("--limit", type=int, default=200, help="max sessions to load (default 200, 0=all)")
    p_audit.add_argument("--judge", action="store_true", help="LLM-judge UNCERTAIN rules via `claude -p`")
    p_audit.add_argument("--out", help="write markdown report to file instead of stdout")
    p_audit.set_defaults(fn=cmd_audit)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
