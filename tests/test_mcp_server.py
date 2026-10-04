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

from reporadar_local.mcp_server import create_server, main, preflight_path, scan_paths_for_agent


def init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    (path / "README.md").write_text("# demo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


class TestMCPAdapter(unittest.TestCase):
    def test_preflight_returns_policy_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "demo"
            repo.mkdir()
            init_repo(repo)
            payload = preflight_path(str(repo), intent="publish")
            self.assertEqual(payload["schema_version"], "reporadar_local.preflight/v1")
            self.assertEqual(payload["repository"]["name"], "demo")
            self.assertEqual(payload["decision"], "review")
            self.assertEqual(payload["reasons"][0]["signal"], "no_upstream")

    def test_scan_returns_versioned_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "demo"
            repo.mkdir()
            init_repo(repo)
            report = scan_paths_for_agent([tmp], max_depth=2, workers=1)
            self.assertEqual(report["schema_version"], "reporadar_local.agent/v1")
            self.assertEqual(report["summary"]["total"], 1)

    def test_invalid_inputs_fail_loudly(self) -> None:
        with self.assertRaises(ValueError):
            scan_paths_for_agent(["/definitely/not/here"])
        with self.assertRaises(ValueError):
            scan_paths_for_agent([], max_depth=-1)
        with self.assertRaises(ValueError):
            preflight_path(".", intent="deploy")

    def test_create_server_marks_tools_read_only(self) -> None:
        class FakeToolAnnotations:
            def __init__(self, read_only_hint=False, open_world_hint=True) -> None:
                self.read_only_hint = read_only_hint
                self.open_world_hint = open_world_hint

        class FakeMCPServer:
            def __init__(self, name: str, instructions: str = "") -> None:
                self.name = name
                self.instructions = instructions
                self.tools: list[tuple[str, dict]] = []

            def tool(self, **kwargs):
                def deco(fn):
                    self.tools.append((fn.__name__, kwargs))
                    return fn
                return deco

            def run(self) -> None:
                pass

        fake_server_module = types.ModuleType("mcp.server")
        fake_server_module.MCPServer = FakeMCPServer
        fake_types_module = types.ModuleType("mcp.types")
        fake_types_module.ToolAnnotations = FakeToolAnnotations
        fake_mcp_module = types.ModuleType("mcp")
        fake_mcp_module.server = fake_server_module
        fake_mcp_module.types = fake_types_module
        with patch.dict(sys.modules, {
            "mcp": fake_mcp_module,
            "mcp.server": fake_server_module,
            "mcp.types": fake_types_module,
        }):
            server = create_server()

        self.assertEqual([name for name, _ in server.tools],
                         ["repository_preflight", "scan_repositories"])
        for _name, metadata in server.tools:
            annotations = metadata["annotations"]
            self.assertTrue(annotations.read_only_hint)
            self.assertFalse(annotations.open_world_hint)

    def test_missing_optional_sdk_has_clear_error(self) -> None:
        with patch.dict(sys.modules, {"mcp": None, "mcp.server": None, "mcp.types": None}):
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
                        "repository_preflight",
                        {"path": str(repo), "intent": "publish"},
                    )
                    self.assertEqual(result.structured_content["schema_version"],
                                     "reporadar_local.preflight/v1")
                    self.assertEqual(result.structured_content["repository"]["name"], "demo")
                    self.assertEqual(result.structured_content["decision"], "review")

            asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
