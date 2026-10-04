# reporadar Agent Protocol

reporadar separates **observation** from **policy**. The scanner reports facts; preflight evaluates those facts for a specific intent.

## Observation: `reporadar.agent/v1`

Produced by `reporadar --agent` and MCP `scan_repositories`.

Each repository includes branch/upstream state, ahead/behind counts, stash count, last commit metadata, HEAD identity, structural status/stash fingerprints, and working-tree totals split into staged, unstaged, untracked, and conflicted entries.

Up to 200 changed-path records are included with index/worktree status and rename origin when applicable. `details_truncated=true` means the repository has more path records than were emitted.

The legacy `--json` shape is deliberately unchanged.

### Compatibility

`agent/v1` is additive-compatible: new optional fields may appear, but existing fields retain their meaning. Breaking semantic or structural changes require a new schema version.

Fingerprints are **structural observations, not content-integrity hashes**. They can reveal branch/status-shape changes, but are not proof that dirty file contents are byte-for-byte unchanged.

## Policy: `reporadar.preflight/v1`

Produced by `reporadar --preflight <intent>` and MCP `repository_preflight`.

Supported intents:

- `read`: only an unreadable repository blocks inspection.
- `modify`: conflicts block; local work, branch-history risk, detached HEAD, or stashes require review.
- `commit`: conflicts and detached HEAD block; local work and branch-history risks require review.
- `publish`: conflicts, divergence, being behind upstream, or detached HEAD block; dirty state, missing upstream, or stashes require review.

Decisions are `allow`, `review`, or `block`. Every non-allow reason includes a stable signal and a recommended action.

These decisions are guardrails, not authorization. Agents must still respect user instructions and host permission boundaries.

## MCP

Install with `pip install "reporadar[mcp]"`, then run `reporadar-mcp` over stdio.

Both MCP tools declare `read_only_hint=true` and `open_world_hint=false`. These annotations help compliant clients with confirmation UX; they are hints, not a security boundary.
