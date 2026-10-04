# reporadar

**One command to see the state of every Git repository on your machine, plus a read-only preflight sensor for coding agents.**

> Distribution name: `reporadar-local` · CLI: `reporadar` · Python package: `reporadar_local`

The distribution and import names are intentionally distinct from other projects already using the RepoRadar name. The CLI and protocol names stay short and stable.

## Install

Until a PyPI release is published, install from GitHub:

```bash
pip install git+https://github.com/yvichyi/reporadar
```

For MCP:

```bash
git clone https://github.com/yvichyi/reporadar
cd reporadar
pip install '.[mcp]'
reporadar-mcp
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

The human table remains fast, colored, cross-platform, and read-only.

## Agent observation

`reporadar --agent` emits `reporadar.agent/v1` with:

- generic `ready / review / blocked` signals;
- exact changed paths, capped at 200;
- staged, unstaged, untracked, and conflicted counts;
- HEAD identity and structural Git-status/stash fingerprints;
- branch sync, stash, and last-commit metadata.

The legacy `--json` key set is preserved.

## Agent preflight

```bash
reporadar --preflight read
reporadar --preflight modify
reporadar --preflight commit
reporadar --preflight publish
```

`reporadar.preflight/v1` returns `allow`, `review`, or `block` with explicit reasons and recommended actions. Policy is deliberately conservative around user-owned local work, conflicts, detached HEADs, divergence, stashes, and publish risk.

See [docs/AGENT_PROTOCOL.md](docs/AGENT_PROTOCOL.md).

## MCP

The stdio server exposes:

- `repository_preflight(path=".", intent="modify")`
- `scan_repositories(paths=None, max_depth=4)`

Both tools declare MCP `read_only_hint=true` and `open_world_hint=false`. MCP is only an adapter. The dependency-free scanner and versioned protocols remain the source of truth.

## Read-only guarantee

reporadar only observes repository state. It never runs push, pull, reset, checkout, stash mutation, commit, add, or any other Git write operation.

## Development

```bash
git clone https://github.com/yvichyi/reporadar
cd reporadar
python -m unittest discover -s tests -v
```

CI tests Python 3.10, 3.12, and 3.14 with and without the official MCP SDK, then builds and installs the wheel in a clean working directory.

## License

MIT
