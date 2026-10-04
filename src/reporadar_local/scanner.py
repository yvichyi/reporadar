"""Find git repositories and collect their status, in parallel."""

from __future__ import annotations

import hashlib
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .model import FileChange, RepoStatus

GIT_TIMEOUT = 10
MAX_CHANGE_DETAILS = 200

SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", ".tox", ".cache", ".mypy_cache",
    ".pytest_cache", "__pycache__", ".idea", ".vscode", "dist", "build",
    "target", "vendor", "bower_components", "site-packages", "$RECYCLE.BIN",
    "System Volume Information", "AppData",
}


def find_repos(roots: list[Path], max_depth: int = 4) -> list[Path]:
    """Walk each root looking for directories containing a .git entry."""
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


def _remember_change(st: RepoStatus, change: FileChange) -> None:
    if len(st.change_files) < MAX_CHANGE_DETAILS:
        st.change_files.append(change)
    else:
        st.change_details_truncated = True


def _count_xy(st: RepoStatus, xy: str) -> None:
    if len(xy) >= 1 and xy[0] != ".":
        st.staged += 1
    if len(xy) >= 2 and xy[1] != ".":
        st.unstaged += 1


def _parse_porcelain_v2_z(out: str, st: RepoStatus) -> None:
    records = out.split("\0")
    i = 0
    while i < len(records):
        record = records[i]
        i += 1
        if not record:
            continue

        if record.startswith("# branch.oid "):
            oid = record[len("# branch.oid "):]
            st.head_oid = None if oid.startswith("(") else oid
            continue
        if record.startswith("# branch.head "):
            st.branch = record[len("# branch.head "):]
            continue
        if record.startswith("# branch.upstream "):
            st.upstream = record[len("# branch.upstream "):]
            continue
        if record.startswith("# branch.ab "):
            fields = record[len("# branch.ab "):].split()
            try:
                st.ahead = abs(int(fields[0]))
                st.behind = abs(int(fields[1]))
            except (IndexError, ValueError):
                pass
            continue

        if record.startswith("1 "):
            fields = record.split(" ", 8)
            if len(fields) < 9:
                continue
            xy, path = fields[1], fields[8]
            st.changed += 1
            _count_xy(st, xy)
            _remember_change(st, FileChange(path, "tracked", xy[0], xy[1]))
            continue

        if record.startswith("2 "):
            fields = record.split(" ", 9)
            if len(fields) < 10:
                continue
            xy, path = fields[1], fields[9]
            original = records[i] if i < len(records) else None
            if i < len(records):
                i += 1
            st.changed += 1
            _count_xy(st, xy)
            kind = "renamed" if "R" in xy else "copied"
            _remember_change(st, FileChange(path, kind, xy[0], xy[1], original))
            continue

        if record.startswith("u "):
            fields = record.split(" ", 10)
            if len(fields) < 11:
                continue
            xy, path = fields[1], fields[10]
            st.changed += 1
            st.conflicted += 1
            _remember_change(st, FileChange(path, "conflict", xy[0], xy[1]))
            continue

        if record.startswith("? "):
            path = record[2:]
            st.changed += 1
            st.untracked += 1
            _remember_change(st, FileChange(path, "untracked", "?", "?"))


def inspect_repo(path: Path) -> RepoStatus:
    """Collect the full status of one repository using read-only git calls."""
    st = RepoStatus(path=path)

    rc, status_out = _run_git(["status", "--porcelain=v2", "--branch", "-z"], path)
    if rc != 0:
        st.error = (
            (status_out or "git status failed").strip().splitlines()[0]
            if status_out else "git status failed"
        )
        return st

    st.status_fingerprint = hashlib.sha256(status_out.encode("utf-8")).hexdigest()
    _parse_porcelain_v2_z(status_out, st)

    rc, log_out = _run_git(["log", "-1", "--format=%ct%x1f%s"], path)
    if rc == 0 and "\x1f" in log_out:
        ts_raw, subject = log_out.split("\x1f", 1)
        st.last_commit_subject = subject.strip()
        try:
            st.last_commit_ts = float(ts_raw.strip())
        except ValueError:
            pass

    rc, stash_out = _run_git(["stash", "list", "--format=%H"], path)
    if rc == 0:
        stash_hashes = [ln.strip() for ln in stash_out.splitlines() if ln.strip()]
        st.stashes = len(stash_hashes)
        st.stash_fingerprint = hashlib.sha256(
            "\n".join(stash_hashes).encode("ascii", errors="ignore")
        ).hexdigest()

    return st


def scan(
    roots: list[Path], max_depth: int = 4, workers: int | None = None,
) -> list[RepoStatus]:
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
