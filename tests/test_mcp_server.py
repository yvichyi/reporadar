from __future__ import annotations

import asyncio
import io
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from reporadar.mcp_server import create_server, main, preflight_path, scan_paths_for_agent


def init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    (path / "README.md").write_text("# demo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


class TestMCPAdapter(unittest.TestCase):
    def test_preflight_returns_agent_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "demo"
            repo.mkdir()
            init_repo(repo)
            payload = preflight_path(str(repo))
            self.assertEqual(payload["name"], "demo")
            self.assertEqual(payload["agent"]["state"], "review")
            self.assertIn("no_upstream", payload["agent"]["signals"])

    def test_scan_returns_versioned_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "demo"
            repo.mkdir()
            init_repo(repo)
            report = scan_paths_for_agent([tmp], max_depth=2, workers=1)
            self.assertEqual(report["schema_version"], "reporadar.agent/v1")
            self.assertEqual(report["summary"]["total"], 1)

    def test_invalid_inputs_fail_loudly(self) -> None:
        with self.assertRaises(ValueError):
            scan_paths_for_agent(["/definitely/not/here"])
        with self.assertRaises(ValueError):
            scan_paths_for_agent([], max_depth=-1)

    def test_create_server_exposes_two_read_only_tools(self) -> None:
        class FakeMCPServer:
            def __init__(self, name: str, instructions: str = "") -> None:
                self.name = name
                self.instructions = instructions
                self.tools: list[str] = []

            def tool(self):
                def deco(fn):
                    self.tools.append(fn.__name__)
                    return fn
                return deco

            def run(self) -> None:
                pass

        fake_server_module = types.ModuleType("mcp.server")
        fake_server_module.MCPServer = FakeMCPServer
        fake_mcp_module = types.ModuleType("mcp")
        fake_mcp_module.server = fake_server_module
        with patch.dict(sys.modules, {"mcp": fake_mcp_module, "mcp.server": fake_server_module}):
            server = create_server()
        self.assertEqual(server.name, "reporadar")
        self.assertEqual(server.tools, ["repository_preflight", "scan_repositories"])
        self.assertIn("Read-only", server.instructions)

    def test_missing_optional_sdk_has_clear_error(self) -> None:
        with patch.dict(sys.modules, {"mcp": None, "mcp.server": None}):
            err = io.StringIO()
            with redirect_stderr(err):
                code = main()
        self.assertEqual(code, 2)
        self.assertIn('pip install "reporadar[mcp]"', err.getvalue())

    def test_real_mcp_sdk_can_call_preflight_when_installed(self) -> None:
        try:
            from mcp import Client
        except ImportError:
            self.skipTest("official MCP SDK is not installed in the local test environment")

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "demo"
            repo.mkdir()
            init_repo(repo)

            async def exercise() -> None:
                async with Client(create_server()) as client:
                    result = await client.call_tool(
                        "repository_preflight", {"path": str(repo)}
                    )
                    self.assertEqual(result.structured_content["name"], "demo")
                    self.assertEqual(
                        result.structured_content["agent"]["state"], "review"
                    )

            asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
