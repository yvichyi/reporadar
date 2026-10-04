"""Tests for the versioned Agent protocol."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from reporadar_local.agent import SCHEMA_VERSION, build_agent_report, classify_repo
from reporadar_local.cli import main
from reporadar_local.model import RepoStatus


class TestAgentProtocol(unittest.TestCase):
    def test_ready_requires_clean_synced_repo(self) -> None:
        repo = RepoStatus(path=Path("/tmp/ready"), branch="main", upstream="origin/main")
        self.assertEqual(classify_repo(repo), {"state": "ready", "signals": []})

    def test_conflicts_are_blocking(self) -> None:
        repo = RepoStatus(path=Path("/tmp/conflict"), branch="main", conflicted=1, changed=1)
        state = classify_repo(repo)
        self.assertEqual(state["state"], "blocked")
        self.assertEqual(state["signals"], ["merge_conflicts"])

    def test_review_signals_are_explicit(self) -> None:
        repo = RepoStatus(
            path=Path("/tmp/review"),
            branch="main",
            upstream="origin/main",
            changed=2,
            ahead=1,
            stashes=1,
        )
        state = classify_repo(repo)
        self.assertEqual(state["state"], "review")
        self.assertEqual(
            state["signals"],
            ["dirty_worktree", "ahead_of_upstream", "stashes_present"],
        )

    def test_report_has_versioned_envelope_and_summary(self) -> None:
        repos = [
            RepoStatus(path=Path("/tmp/ready"), branch="main", upstream="origin/main"),
            RepoStatus(path=Path("/tmp/review"), branch="main", changed=1),
            RepoStatus(path=Path("/tmp/blocked"), branch="main", error="boom"),
        ]
        report = build_agent_report(repos, generated_at="2026-10-03T00:00:00Z")
        self.assertEqual(report["schema_version"], SCHEMA_VERSION)
        self.assertEqual(report["generated_at"], "2026-10-03T00:00:00Z")
        self.assertEqual(
            report["summary"],
            {"total": 3, "ready": 1, "review": 1, "blocked": 1},
        )

    def test_cli_agent_output(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="reporadar-agent-test-"))
        self.addCleanup(shutil.rmtree, root, True)
        repo = root / "demo"
        repo.mkdir()
        subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        (repo / "README.md").write_text("# demo\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main([str(root), "--agent"])
        data = json.loads(buf.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(data["schema_version"], SCHEMA_VERSION)
        self.assertEqual(data["summary"]["total"], 1)
        self.assertEqual(data["repositories"][0]["name"], "demo")

    def test_empty_agent_scan_is_valid_protocol(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="reporadar-agent-empty-"))
        self.addCleanup(shutil.rmtree, root, True)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main([str(root), "--agent"])
        data = json.loads(buf.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(
            data["summary"],
            {"total": 0, "ready": 0, "review": 0, "blocked": 0},
        )


if __name__ == "__main__":
    unittest.main()
