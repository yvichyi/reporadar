"""Stable machine-facing protocol for coding agents and automation."""

from __future__ import annotations

from datetime import datetime, timezone

from .model import RepoStatus

SCHEMA_VERSION = "reporadar.agent/v1"


def classify_repo(repo: RepoStatus) -> dict[str, object]:
    """Return a conservative agent-facing state and the signals behind it.

    blocked means the repository should not be treated as a normal clean
    working copy. review means an agent should inspect the listed signals
    before making broad changes. ready is reserved for a clean, synced
    working copy with no stash or scanner error.
    """
    signals: list[str] = []

    if repo.error:
        signals.append("scan_error")
        return {"state": "blocked", "signals": signals}

    if repo.has_conflicts:
        signals.append("merge_conflicts")
        return {"state": "blocked", "signals": signals}

    if repo.is_dirty:
        signals.append("dirty_worktree")

    if repo.ahead and repo.behind:
        signals.append("diverged_from_upstream")
    else:
        if repo.ahead:
            signals.append("ahead_of_upstream")
        if repo.behind:
            signals.append("behind_upstream")

    if repo.branch == "(detached)":
        signals.append("detached_head")
    elif not repo.has_upstream:
        signals.append("no_upstream")

    if repo.stashes:
        signals.append("stashes_present")

    return {
        "state": "review" if signals else "ready",
        "signals": signals,
    }


def repo_payload(repo: RepoStatus) -> dict[str, object]:
    """Serialize one repository into the v1 agent protocol."""
    return {
        "path": str(repo.path),
        "name": repo.name,
        "branch": repo.branch,
        "upstream": repo.upstream,
        "working_tree": {
            "changed": repo.changed,
            "conflicted": repo.conflicted,
            "dirty": repo.is_dirty,
        },
        "sync": {
            "ahead": repo.ahead,
            "behind": repo.behind,
            "unpushed": repo.is_unpushed,
            "has_upstream": repo.has_upstream,
        },
        "stashes": repo.stashes,
        "activity": {
            "last_commit_ts": repo.last_commit_ts,
            "last_commit_subject": repo.last_commit_subject,
        },
        "error": repo.error,
        "agent": classify_repo(repo),
    }


def build_agent_report(
    repos: list[RepoStatus], generated_at: str | None = None,
) -> dict[str, object]:
    """Build the stable top-level envelope used by reporadar --agent."""
    items = [repo_payload(repo) for repo in repos]
    counts = {"ready": 0, "review": 0, "blocked": 0}
    for item in items:
        state = item["agent"]["state"]  # type: ignore[index]
        counts[str(state)] += 1

    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "summary": {
            "total": len(items),
            **counts,
        },
        "repositories": items,
    }
