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
from .report import render, to_json
from .rules import file_tokens, parse_all
from .transcripts import DEFAULT_PROJECTS_DIR, discover, filter_by_date


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


def _emit(out: str, out_path: str | None) -> int:
    if out_path:
        Path(out_path).write_text(out)
        print(f"report written to {out_path}")
    else:
        print(out)
    return 0


def _valid_iso(value: str, flag: str) -> bool:
    from datetime import datetime

    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        print(f"{flag} must be an ISO date (YYYY-MM-DD[THH:MM:SS]), got {value!r}", file=sys.stderr)
        return False


def cmd_audit(args: argparse.Namespace) -> int:
    paths = [Path(p) for p in args.files] or default_claude_mds()
    if not paths:
        print("no CLAUDE.md found; pass paths explicitly", file=sys.stderr)
        return 1
    since, until = args.since or "", args.until or ""
    for value, flag in ((since, "--since"), (until, "--until")):
        if value and not _valid_iso(value, flag):
            return 1
    rules = parse_all(paths)
    if not rules:
        print("no rules parsed from input files", file=sys.stderr)
        return 1

    # date bounds disable the load limit — limiting first would sample only the
    # newest sessions and silently starve the older era out of a capability diff
    load_limit = 0 if (since or until) else args.limit
    projects_dir = Path(args.transcripts) if args.transcripts else DEFAULT_PROJECTS_DIR
    if args.transcripts and projects_dir.is_dir() and list(projects_dir.glob("*.jsonl")):
        # a directory of .jsonl files directly (fixtures / exported logs)
        from .transcripts import load_project

        sessions = load_project(projects_dir, limit=load_limit)
    else:
        sessions = discover(all_projects=args.all_projects, limit=load_limit, projects_dir=projects_dir)
    if not sessions:
        print(
            f"no transcripts found under {projects_dir} for this project.\n"
            f"hint: run from the directory whose sessions you want to audit, or use "
            f"--all-projects / --transcripts DIR",
            file=sys.stderr,
        )
        return 1
    if since or until:
        undated = sum(1 for s in sessions if not s.started)
        sessions = filter_by_date(sessions, since=since, until=until)
        if undated:
            print(f"note: {undated} sessions had no timestamp and were excluded from the era slice",
                  file=sys.stderr)
        if args.limit:
            sessions = sessions[: args.limit]
    if not sessions:
        print("no sessions left after --since/--until filtering", file=sys.stderr)
        return 1

    evidences = run_audit(rules, sessions)
    if args.judge:
        from .judge import judge_uncertain

        evidences = judge_uncertain(evidences, sessions)

    if args.json:
        out = to_json(evidences, len(sessions), file_tokens=file_tokens(paths))
    else:
        out = render(evidences, len(sessions), file_tokens=file_tokens(paths))
    return _emit(out, args.out)


def _load_report(path: str) -> dict | None:
    import json

    try:
        blob = json.loads(Path(path).read_text())
    except OSError as e:
        print(f"cannot read {path}: {e}", file=sys.stderr)
        return None
    except json.JSONDecodeError:
        print(f"{path} is not valid JSON — pass a report from `molt audit --json`", file=sys.stderr)
        return None
    if not isinstance(blob, dict) or not isinstance(blob.get("rules"), list):
        print(f"{path} is not a molt audit report (missing 'rules')", file=sys.stderr)
        return None
    return blob


def cmd_diff(args: argparse.Namespace) -> int:
    from .diffcmd import diff_reports, render_diff

    old, new = _load_report(args.old), _load_report(args.new)
    if old is None or new is None:
        return 1
    print(render_diff(diff_reports(old, new)))
    return 0


def _claude_runner(model: str, timeout: int, permission_mode: str):
    """Real trial runner: sandbox dir + scaffold variant + `claude -p` + shell check.

    Returns True/False from the task's check command, or None when the agent
    invocation itself failed (nonzero exit, timeout) — infrastructure noise
    must not masquerade as a task verdict."""
    import subprocess
    import tempfile

    def run(scaffold: str, task: dict):
        with tempfile.TemporaryDirectory(prefix="molt-ablate-") as tmp:
            Path(tmp, "CLAUDE.md").write_text(scaffold)
            try:
                agent = subprocess.run(
                    ["claude", "-p", task["prompt"], "--model", model,
                     "--permission-mode", permission_mode],
                    cwd=tmp, capture_output=True, text=True, timeout=timeout,
                )
                if agent.returncode != 0:
                    return None
                check = subprocess.run(
                    task["check"], shell=True, cwd=tmp, capture_output=True, timeout=60,
                )
                return check.returncode == 0
            except (subprocess.TimeoutExpired, OSError):
                return None

    return run


def cmd_ablate(args: argparse.Namespace) -> int:
    import json
    import shutil

    from .ablate import ablate, render_ablation
    from .rules import parse_file

    if not shutil.which("claude"):
        print("`claude` CLI not found on PATH; ablation needs it", file=sys.stderr)
        return 1
    scaffold_path = Path(args.file).resolve()
    if scaffold_path == (Path.home() / ".claude" / "CLAUDE.md").resolve():
        print(
            "cannot ablate the global ~/.claude/CLAUDE.md: `claude -p` loads it in BOTH\n"
            "trial arms, so every rule would read NO_EFFECT regardless of truth.\n"
            "Copy the rules you want to test into a project-level CLAUDE.md and ablate that.",
            file=sys.stderr,
        )
        return 1
    scaffold_text = scaffold_path.read_text()
    # parse THIS file only — @imported rules carry line numbers from other
    # files and the sandbox only ships one CLAUDE.md, so ablating them would
    # slice the wrong lines and compare identical arms
    rules = parse_file(scaffold_path)
    if args.rule:
        rules = [r for r in rules if any(f.lower() in r.text.lower() for f in args.rule)]
    if not rules:
        print("no rules matched", file=sys.stderr)
        return 1
    try:
        tasks = json.loads(Path(args.tasks).read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"cannot read tasks file {args.tasks}: {e}", file=sys.stderr)
        return 1
    if (
        not isinstance(tasks, list)
        or not tasks
        or not all(isinstance(t, dict) and "prompt" in t and "check" in t for t in tasks)
    ):
        print("tasks file must be a non-empty JSON list of {\"prompt\": ..., \"check\": ...}",
              file=sys.stderr)
        return 1
    runs = (len(rules) + 1) * len(tasks) * args.trials
    if runs > 100 and not args.yes:
        print(
            f"{runs} real agent runs requested — that's real time and money.\n"
            f"Narrow with --rule/--trials, or pass --yes to proceed.",
            file=sys.stderr,
        )
        return 1
    print(f"ablating {len(rules)} rule(s): {runs} agent runs (model={args.model})…", file=sys.stderr)
    results = ablate(rules, scaffold_text, tasks,
                     _claude_runner(args.model, args.timeout, args.permission_mode),
                     trials=args.trials)
    return _emit(render_ablation(results), args.out)


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
    p_audit.add_argument("--json", action="store_true", help="machine-readable output (for `molt diff`)")
    p_audit.add_argument("--since", help="only sessions started on/after this ISO date")
    p_audit.add_argument("--until", help="only sessions started before this ISO date")
    p_audit.add_argument("--out", help="write report to file instead of stdout")
    p_audit.set_defaults(fn=cmd_audit)

    p_diff = sub.add_parser("diff", help="capability diff between two `audit --json` reports")
    p_diff.add_argument("old", help="old-era report JSON")
    p_diff.add_argument("new", help="new-era report JSON")
    p_diff.set_defaults(fn=cmd_diff)

    p_ab = sub.add_parser("ablate", help="A/B a scaffold file's rules against a task suite (uses `claude -p`)")
    p_ab.add_argument("file", help="scaffold file whose rules to ablate")
    p_ab.add_argument("--tasks", required=True, help="JSON file: [{\"prompt\": ..., \"check\": <shell cmd>}]")
    p_ab.add_argument("--rule", action="append", help="only ablate rules containing this substring (repeatable)")
    p_ab.add_argument("--trials", type=int, default=3, help="trials per task per variant (default 3)")
    p_ab.add_argument("--model", default="haiku", help="model for trial runs (default haiku)")
    p_ab.add_argument("--timeout", type=int, default=300, help="per-run timeout seconds")
    p_ab.add_argument("--permission-mode", default="acceptEdits",
                      help="claude -p permission mode for sandbox runs (default acceptEdits)")
    p_ab.add_argument("--yes", action="store_true", help="proceed even when >100 agent runs")
    p_ab.add_argument("--out", help="write report to file")
    p_ab.set_defaults(fn=cmd_ablate)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
