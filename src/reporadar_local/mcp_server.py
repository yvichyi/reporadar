"""Optional MCP adapter for reporadar's read-only agent protocol."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .agent import build_agent_report
from .policy import evaluate_repo
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
    if max_depth < 0:
        raise ValueError("max_depth must be >= 0")
    return build_agent_report(scan(_roots(paths), max_depth=max_depth, workers=workers))


def preflight_path(path: str = ".", intent: str = "modify") -> dict[str, object]:
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    if not (root / ".git").exists():
        raise ValueError(f"not a git repository root: {root}")
    return evaluate_repo(inspect_repo(root), intent=intent)


def create_server() -> Any:
    try:
        from mcp.server import MCPServer
        from mcp.types import ToolAnnotations
    except ImportError as exc:
        raise RuntimeError(
            'MCP support is optional. Install it with: pip install "reporadar[mcp]"'
        ) from exc

    read_only = ToolAnnotations(read_only_hint=True, open_world_hint=False)
    mcp = MCPServer(
        "reporadar",
        instructions=(
            "Read-only Git repository state for coding agents. "
            "Use repository_preflight before modifying, committing, or publishing, "
            "and scan_repositories to inspect multiple working copies."
        ),
    )

    @mcp.tool(title="Repository preflight", annotations=read_only)
    def repository_preflight(
        path: str = ".",
        intent: str = "modify",
    ) -> dict[str, object]:
        """Inspect a repository and return allow/review/block with explicit reasons."""
        return preflight_path(path, intent=intent)

    @mcp.tool(title="Scan repositories", annotations=read_only)
    def scan_repositories(
        paths: list[str] | None = None,
        max_depth: int = 4,
    ) -> dict[str, object]:
        """Scan one or more directory trees and return versioned repository state."""
        return scan_paths_for_agent(paths=paths, max_depth=max_depth)

    return mcp


def main() -> int:
    try:
        server = create_server()
    except RuntimeError as exc:
        print(f"reporadar-mcp: {exc}", file=sys.stderr)
        return 2
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
