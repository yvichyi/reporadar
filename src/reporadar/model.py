"""Data model for a single repository's status."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class FileChange:
    """One worktree entry from git status porcelain v2."""

    path: str
    kind: str
    index_status: str = "."
    worktree_status: str = "."
    original_path: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "path": self.path,
            "kind": self.kind,
            "index_status": self.index_status,
            "worktree_status": self.worktree_status,
            "original_path": self.original_path,
        }


@dataclass
class RepoStatus:
    """Everything reporadar knows about one working copy."""

    path: Path
    branch: str = ""
    head_oid: str | None = None
    upstream: str | None = None
    ahead: int = 0
    behind: int = 0
    changed: int = 0
    staged: int = 0
    unstaged: int = 0
    untracked: int = 0
    conflicted: int = 0
    stashes: int = 0
    last_commit_ts: float | None = None
    last_commit_subject: str = ""
    error: str | None = None
    change_files: list[FileChange] = field(default_factory=list)
    change_details_truncated: bool = False
    status_fingerprint: str | None = None
    stash_fingerprint: str | None = None

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def is_dirty(self) -> bool:
        return self.changed > 0

    @property
    def has_conflicts(self) -> bool:
        return self.conflicted > 0

    @property
    def is_unpushed(self) -> bool:
        return self.ahead > 0

    @property
    def has_upstream(self) -> bool:
        return self.upstream is not None

    def to_dict(self) -> dict:
        """Legacy JSON shape. Keep this stable for existing --json consumers."""
        return {
            "path": str(self.path),
            "name": self.name,
            "branch": self.branch,
            "upstream": self.upstream,
            "ahead": self.ahead,
            "behind": self.behind,
            "changed": self.changed,
            "conflicted": self.conflicted,
            "dirty": self.is_dirty,
            "stashes": self.stashes,
            "last_commit_ts": self.last_commit_ts,
            "last_commit_subject": self.last_commit_subject,
            "error": self.error,
        }
