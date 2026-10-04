# reporadar

**One command to see the state of every Git repository on your machine, with a read-only sensor layer for coding agents.**

```text
REPO           BRANCH      STATUS       SYNC         LAST COMMIT  STASH
-------------  ----------  -----------  -----------  -----------  -----
web-app        main        ● 3 changes  ⇡2           4m ago       ⚑1
alpha          main        ✓ clean      ✓ synced     2h ago       —
legacy-tool    (detached)  ✓ clean      —            8mo ago      —
```

## Install

```bash
pip install reporadar

# optional MCP v2 adapter
pip install "reporadar[mcp]"
```

Python 3.10+ and Git are required. The core package has zero runtime dependencies.

## Human CLI

```bash
reporadar
reporadar ~/projects ~/work
reporadar --dirty
reporadar --ahead
reporadar --stale 90
reporadar --json
```

The table remains fast, colored, cross-platform, and completely read-only.

## Agent observation

`reporadar --agent` emits the versioned `reporadar.agent/v1` protocol. It includes:

- generic `ready / review / blocked` signals;
- exact changed paths, capped at 200 entries;
- staged, unstaged, untracked, and conflicted counts;
- HEAD identity and structural Git-status/stash fingerprints;
- branch sync, stash, and last-commit metadata.

The old `--json` shape remains unchanged for compatibility.

## Agent preflight policy

Observation and policy are intentionally separate. Tell reporadar what the agent plans to do:

```bash
reporadar --preflight read
reporadar --preflight modify
reporadar --preflight commit
reporadar --preflight publish
```

Preflight emits `reporadar.preflight/v1` with an `allow`, `review`, or `block` decision, explicit reasons, and recommended actions. It is deliberately conservative around user-owned local work, conflicts, detached HEADs, branch divergence, stashes, and publish risk.

See [docs/AGENT_PROTOCOL.md](docs/AGENT_PROTOCOL.md) for schema and compatibility guarantees.

## MCP

```bash
pip install "reporadar[mcp]"
reporadar-mcp
```

The stdio server exposes two tools:

- `repository_preflight(path=".", intent="modify")`: inspect one repository and apply an intent-aware safety policy.
- `scan_repositories(paths=None, max_depth=4)`: observe one or more directory trees using `agent/v1`.

Both are explicitly annotated as read-only and closed-world for MCP clients. MCP is only an adapter; the dependency-free scanner and versioned protocols remain the source of truth.

## Why this exists

Coding agents should not infer repository safety from a pretty terminal table or silently assume a clean workspace. reporadar gives them a small, deterministic sensor surface before they touch code.

It never runs push, pull, reset, checkout, stash mutation, or any other write operation.

## Development

```bash
git clone https://github.com/yvichyi/reporadar
cd reporadar
python -m unittest discover -s tests -v
```

CI covers the oldest supported Python plus newer runtimes, with and without the official MCP SDK.

## License

MIT
