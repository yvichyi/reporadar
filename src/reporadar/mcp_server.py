"""Optional MCP adapter for reporadar's read-only agent protocol."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .agent import build_agent_report, repo_payload
from .scanner import inspect_repo, scan


def _roots(paths: list[str] | None) -> list[Path]:
    roots = [Path(p).expanduser() for p in paths] if paths else [Path.cwd()]
    missing = [str(path) for path in roots if not path.is_dir()]
    if missing:
        raise ValueError(f"not a directory: {', '.join(missing)}")
    return roots


def scan_paths_for_agent(
    paths: list[str] | None = None,
    max_depth: int = 4,
    workers: int | None = None,
) -> dict[str, object]:
    """Scan repository roots and return the stable reporadar agent envelope."""
    if max_depth < 0:
        raise ValueError("max_depth must be >= 0")
    repos = scan(_roots(paths), max_depth=max_depth, workers=workers)
    return build_agent_report(repos)


def preflight_path(path: str = ".") -> dict[str, object]:
    """Inspect one repository root before an agent modifies it."""
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    if not (root / ".git").exists():
        raise ValueError(f"not a git repository root: {root}")
    return repo_payload(inspect_repo(root))


def create_server() -> Any:
    """Create the optional MCP v2 server without adding a core dependency."""
    try:
        from mcp.server import MCPServer
    except ImportError as exc:
        raise RuntimeError(
            'MCP support is optional. Install it with: pip install "reporadar[mcp]"'
        ) from exc

    mcp = MCPServer(
        "reporadar",
        instructions=(
            "Read-only Git repository state for coding agents. "
            "Use repository_preflight before modifying a repository, and "
            "scan_repositories to inspect multiple working copies."
        ),
    )

    @mcp.tool()
    def repository_preflight(path: str = ".") -> dict[str, object]:
        """Inspect one repository root and return explicit ready/review/blocked signals."""
        return preflight_path(path)

    @mcp.tool()
    def scan_repositories(
        paths: list[str] | None = None,
        max_depth: int = 4,
    ) -> dict[str, object]:
        """Scan one or more directory trees and return versioned repository state."""
        return scan_paths_for_agent(paths=paths, max_depth=max_depth)

    return mcp


def main() -> int:
    """Run the MCP server over stdio, the SDK's default local transport."""
    try:
        server = create_server()
    except RuntimeError as exc:
        print(f"reporadar-mcp: {exc}", file=sys.stderr)
        return 2
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
