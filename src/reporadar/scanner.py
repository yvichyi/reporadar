"""Find git repositories and collect their status, in parallel."""

from __future__ import annotations

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .model import RepoStatus

GIT_TIMEOUT = 10  # seconds per git invocation

# Directories we never descend into while searching for repos.
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", ".tox", ".cache", ".mypy_cache",
    ".pytest_cache", "__pycache__", ".idea", ".vscode", "dist", "build",
    "target", "vendor", "bower_components", "site-packages", "$RECYCLE.BIN",
    "System Volume Information", "AppData",
}


def find_repos(roots: list[Path], max_depth: int = 4) -> list[Path]:
    """Walk each root looking for directories containing a .git entry.

    Nested repositories inside a repository are still reported. The walk
    never enters SKIP_DIRS or hidden directories.
    """
    repos: list[Path] = []
    seen: set[Path] = set()

    for root in roots:
        root = root.resolve()
        if not root.is_dir():
            continue
        base_depth = len(root.parts)
        for dirpath, dirnames, _filenames in os.walk(root, followlinks=False):
            current = Path(dirpath)
            depth = len(current.parts) - base_depth
            if (current / ".git").exists() and current not in seen:
                seen.add(current)
                repos.append(current)
            # Prune: never enter junk or hidden dirs; respect depth budget.
            dirnames[:] = [
                d for d in dirnames
                if d not in SKIP_DIRS and not d.startswith(".")
            ]
            if depth >= max_depth:
                dirnames[:] = []
    return repos


def _run_git(args: list[str], cwd: Path) -> tuple[int, str]:
    """Run a git command, returning (returncode, stdout). Never raises."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_TIMEOUT,
        )
        return proc.returncode, proc.stdout
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


def inspect_repo(path: Path) -> RepoStatus:
    """Collect the full status of one repository using a few git calls."""
    st = RepoStatus(path=path)

    rc, out = _run_git(["status", "--porcelain=v2", "--branch"], path)
    if rc != 0:
        st.error = (out or "git status failed").strip().splitlines()[0] if out else "git status failed"
        return st

    for line in out.splitlines():
        if line.startswith("# branch.head "):
            st.branch = line.split()[2]
        elif line.startswith("# branch.upstream "):
            st.upstream = line.split()[2]
        elif line.startswith("# branch.ab "):
            fields = line.split()
            try:
                st.ahead = abs(int(fields[2]))   # porcelain emits "+N -M"
                st.behind = abs(int(fields[3]))
            except (IndexError, ValueError):
                pass
        elif line.startswith("u "):
            st.conflicted += 1
            st.changed += 1
        elif line and not line.startswith("#"):
            st.changed += 1

    rc, out = _run_git(["log", "-1", "--format=%cI%x1f%s"], path)
    if rc == 0 and "\x1f" in out:
        ts_raw, subject = out.split("\x1f", 1)
        st.last_commit_subject = subject.strip()
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(ts_raw.strip())
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            st.last_commit_ts = dt.timestamp()
        except ValueError:
            pass
    # else: brand-new repo with no commits yet — leave ts as None.

    rc, out = _run_git(["stash", "list", "--format=%H"], path)
    if rc == 0:
        st.stashes = sum(1 for ln in out.splitlines() if ln.strip())

    return st


def scan(roots: list[Path], max_depth: int = 4, workers: int | None = None) -> list[RepoStatus]:
    """Find and inspect every repository under the given roots."""
    repos = find_repos(roots, max_depth=max_depth)
    if not repos:
        return []
    if workers is None:
        workers = min(32, (os.cpu_count() or 4) * 4)
    results: list[RepoStatus] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(inspect_repo, r): r for r in repos}
        for fut in as_completed(futures):
            results.append(fut.result())
    return results
