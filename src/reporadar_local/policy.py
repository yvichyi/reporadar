"""Intent-aware preflight policy for coding agents."""

from __future__ import annotations

from datetime import datetime, timezone

from .agent import classify_repo, repo_payload
from .model import RepoStatus

SCHEMA_VERSION = "reporadar.preflight/v1"
INTENTS = ("read", "modify", "commit", "publish")
_RANK = {"allow": 0, "review": 1, "block": 2}

_RULES: dict[str, dict[str, str]] = {
    "read": {"scan_error": "block"},
    "modify": {
        "scan_error": "block",
        "merge_conflicts": "block",
        "dirty_worktree": "review",
        "diverged_from_upstream": "review",
        "ahead_of_upstream": "review",
        "behind_upstream": "review",
        "detached_head": "review",
        "stashes_present": "review",
    },
    "commit": {
        "scan_error": "block",
        "merge_conflicts": "block",
        "dirty_worktree": "review",
        "diverged_from_upstream": "review",
        "behind_upstream": "review",
        "detached_head": "block",
        "stashes_present": "review",
    },
    "publish": {
        "scan_error": "block",
        "merge_conflicts": "block",
        "dirty_worktree": "review",
        "diverged_from_upstream": "block",
        "behind_upstream": "block",
        "detached_head": "block",
        "no_upstream": "review",
        "stashes_present": "review",
    },
}

_MESSAGES = {
    "scan_error": (
        "Repository state could not be read reliably.",
        "Fix the Git access or scan error before acting.",
    ),
    "merge_conflicts": (
        "The repository has unresolved merge or rebase conflicts.",
        "Resolve or intentionally isolate the conflict before continuing.",
    ),
    "dirty_worktree": (
        "The working tree contains local changes that may belong to the user.",
        "Inspect changed paths and avoid overwriting or bundling unrelated work.",
    ),
    "diverged_from_upstream": (
        "Local and upstream histories have diverged.",
        "Reconcile the branch deliberately before publishing or broad edits.",
    ),
    "ahead_of_upstream": (
        "Local commits have not been published upstream.",
        "Preserve the existing commits and understand them before adding work.",
    ),
    "behind_upstream": (
        "The local branch is behind its upstream.",
        "Refresh or reconcile upstream state before publishing.",
    ),
    "detached_head": (
        "HEAD is detached, so new commits may be easy to lose.",
        "Create or switch to an intentional branch before committing.",
    ),
    "no_upstream": (
        "The branch has no configured upstream.",
        "Confirm the intended remote and branch before publishing.",
    ),
    "stashes_present": (
        "The repository contains hidden stashed work.",
        "Treat the stash as user-owned state and avoid destructive cleanup.",
    ),
}


def _validate_intent(intent: str) -> str:
    if intent not in INTENTS:
        raise ValueError(f"intent must be one of: {', '.join(INTENTS)}")
    return intent


def evaluate_repo(repo: RepoStatus, intent: str = "modify") -> dict[str, object]:
    """Evaluate observed repository signals against an explicit agent intent."""
    intent = _validate_intent(intent)
    generic = classify_repo(repo)
    signals = list(generic["signals"])  # type: ignore[arg-type]
    decision = "allow"
    reasons: list[dict[str, str]] = []

    for signal in signals:
        disposition = _RULES[intent].get(signal, "allow")
        if _RANK[disposition] > _RANK[decision]:
            decision = disposition
        if disposition != "allow":
            message, action = _MESSAGES[signal]
            reasons.append({
                "signal": signal,
                "disposition": disposition,
                "message": message,
                "recommended_action": action,
            })

    return {
        "schema_version": SCHEMA_VERSION,
        "intent": intent,
        "decision": decision,
        "reasons": reasons,
        "repository": repo_payload(repo),
    }


def build_preflight_report(
    repos: list[RepoStatus],
    intent: str = "modify",
    generated_at: str | None = None,
) -> dict[str, object]:
    """Build a multi-repository preflight report for CLI and automation."""
    intent = _validate_intent(intent)
    items = [evaluate_repo(repo, intent=intent) for repo in repos]
    counts = {"allow": 0, "review": 0, "block": 0}
    for item in items:
        counts[str(item["decision"])] += 1

    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "intent": intent,
        "summary": {"total": len(items), **counts},
        "repositories": items,
    }
