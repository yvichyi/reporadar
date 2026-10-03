"""Command-line entry point for reporadar."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .agent import build_agent_report
from .model import RepoStatus
from .report import enable_windows_vt, render
from .scanner import scan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reporadar",
        description="One command to see the state of every git repository on your machine.",
    )
    parser.add_argument(
        "paths", nargs="*", type=Path, default=None,
        help="directories to scan (default: current directory)",
    )
    parser.add_argument("--depth", type=int, default=4,
                        help="maximum directory depth to search (default: 4)")
    parser.add_argument("--sort", choices=["activity", "name", "dirty"], default="activity",
                        help="row order (default: activity, most recent first)")
    parser.add_argument("--dirty", action="store_true",
                        help="only show repositories with uncommitted changes")
    parser.add_argument("--ahead", action="store_true",
                        help="only show repositories with commits not pushed upstream")
    parser.add_argument("--stale", type=float, metavar="DAYS", default=None,
                        help="only show repositories whose last commit is older than DAYS")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", dest="as_json",
                        help="emit legacy machine-readable JSON array instead of a table")
    output.add_argument("--agent", action="store_true", dest="as_agent",
                        help="emit versioned agent protocol JSON with state signals and summary")
    parser.add_argument("--workers", type=int, default=None,
                        help="parallel git workers (default: auto)")
    parser.add_argument("--no-color", action="store_true",
                        help="disable colored output")
    parser.add_argument("--ascii", action="store_true",
                        help="use ASCII-only glyphs for legacy consoles")
    parser.add_argument("-V", "--version", action="version",
                        version=f"%(prog)s {__version__}")
    return parser


def sort_repos(repos: list[RepoStatus], key: str) -> list[RepoStatus]:
    if key == "name":
        return sorted(repos, key=lambda r: r.name.lower())
    if key == "dirty":
        # Dirtiest and most recently touched first.
        return sorted(
            repos,
            key=lambda r: (not r.is_dirty, -(r.last_commit_ts or 0)),
        )
    return sorted(repos, key=lambda r: -(r.last_commit_ts or 0))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    roots = [p for p in (args.paths or [Path.cwd()])]
    missing = [str(p) for p in roots if not p.is_dir()]
    if missing:
        print(f"reporadar: not a directory: {', '.join(missing)}", file=sys.stderr)
        return 2

    repos = scan(roots, max_depth=args.depth, workers=args.workers)

    if args.dirty:
        repos = [r for r in repos if r.is_dirty]
    if args.ahead:
        repos = [r for r in repos if r.is_unpushed]
    if args.stale is not None:
        import time
        cutoff = time.time() - args.stale * 86400
        repos = [r for r in repos if (r.last_commit_ts or 0) < cutoff]

    repos = sort_repos(repos, args.sort)

    if args.as_json:
        json.dump([r.to_dict() for r in repos], sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    if args.as_agent:
        json.dump(build_agent_report(repos), sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    use_color = not args.no_color and sys.stdout.isatty()
    if use_color:
        enable_windows_vt()

    if not repos:
        print("No git repositories found.")
        return 1

    print(render(repos, color=use_color, ascii_only=args.ascii))
    return 0


if __name__ == "__main__":
    sys.exit(main())
