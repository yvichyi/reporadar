"""Data model for a single repository's status."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class RepoStatus:
    """Everything reporadar knows about one working copy."""

    path: Path
    branch: str = ""              # "(detached)" when HEAD is detached
    upstream: str | None = None
    ahead: int = 0
    behind: int = 0
    changed: int = 0              # staged + unstaged + untracked entries
    conflicted: int = 0           # unresolved merge/rebase entries
    stashes: int = 0
    last_commit_ts: float | None = None   # epoch seconds; None on a repo with no commits
    last_commit_subject: str = ""
    error: str | None = None      # set when git failed on this repo

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
