"""Intent-aware policy and protocol regression tests."""

from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from reporadar_local.agent import repo_payload
from reporadar_local.cli import main
from reporadar_local.model import RepoStatus
from reporadar_local.policy import build_preflight_report, evaluate_repo
from reporadar_local.scanner import inspect_repo


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def init_repo(path: Path) -> None:
    git("init", "-b", "main", cwd=path)
    git("config", "user.email", "test@example.com", cwd=path)
    git("config", "user.name", "Test", cwd=path)
    (path / "README.md").write_text("# demo\n", encoding="utf-8")
    git("add", "README.md", cwd=path)
    git("commit", "-m", "init", cwd=path)


class TestWorkingTreeDetails(unittest.TestCase):
    def test_agent_payload_exposes_paths_counts_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            (repo / "README.md").write_text("# changed\n", encoding="utf-8")
            (repo / "staged file.txt").write_text("staged\n", encoding="utf-8")
            git("add", "staged file.txt", cwd=repo)
            (repo / "untracked file.txt").write_text("untracked\n", encoding="utf-8")

            payload = repo_payload(inspect_repo(repo))
            tree = payload["working_tree"]
            self.assertIsNotNone(payload["snapshot"]["head_oid"])
            self.assertIsNotNone(payload["snapshot"]["status_fingerprint"])
            self.assertEqual(tree["changed"], 3)
            self.assertEqual(tree["staged"], 1)
            self.assertEqual(tree["unstaged"], 1)
            self.assertEqual(tree["untracked"], 1)
            self.assertEqual(
                {item["path"] for item in tree["files"]},
                {"README.md", "staged file.txt", "untracked file.txt"},
            )

    def test_legacy_json_shape_does_not_gain_agent_fields(self) -> None:
        status = RepoStatus(path=Path("/tmp/demo"), branch="main")
        self.assertEqual(
            set(status.to_dict()),
            {
                "path", "name", "branch", "upstream", "ahead", "behind",
                "changed", "conflicted", "dirty", "stashes",
                "last_commit_ts", "last_commit_subject", "error",
            },
        )


class TestPolicy(unittest.TestCase):
    def test_modify_reviews_local_user_work(self) -> None:
        repo = RepoStatus(path=Path("/tmp/demo"), branch="main",
                          upstream="origin/main", changed=1)
        result = evaluate_repo(repo, "modify")
        self.assertEqual(result["decision"], "review")
        self.assertEqual(result["reasons"][0]["signal"], "dirty_worktree")

    def test_conflict_blocks_modify_but_not_read(self) -> None:
        repo = RepoStatus(path=Path("/tmp/demo"), branch="main", changed=1, conflicted=1)
        self.assertEqual(evaluate_repo(repo, "modify")["decision"], "block")
        self.assertEqual(evaluate_repo(repo, "read")["decision"], "allow")

    def test_publish_blocks_behind_and_detached(self) -> None:
        behind = RepoStatus(path=Path("/tmp/behind"), branch="main",
                            upstream="origin/main", behind=1)
        detached = RepoStatus(path=Path("/tmp/detached"), branch="(detached)")
        self.assertEqual(evaluate_repo(behind, "publish")["decision"], "block")
        self.assertEqual(evaluate_repo(detached, "publish")["decision"], "block")

    def test_invalid_intent_fails(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_repo(RepoStatus(path=Path("/tmp/demo")), "deploy")

    def test_report_summary(self) -> None:
        repos = [
            RepoStatus(path=Path("/tmp/a"), branch="main", upstream="origin/main"),
            RepoStatus(path=Path("/tmp/b"), branch="main", changed=1),
            RepoStatus(path=Path("/tmp/c"), branch="main", error="boom"),
        ]
        report = build_preflight_report(repos, "modify", "2026-10-04T00:00:00Z")
        self.assertEqual(report["schema_version"], "reporadar.preflight/v1")
        self.assertEqual(report["summary"], {"total": 3, "allow": 1, "review": 1, "block": 1})

    def test_cli_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "demo"
            repo.mkdir()
            init_repo(repo)
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = main([str(repo), "--preflight", "modify", "--depth", "0"])
            data = json.loads(buf.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(data["schema_version"], "reporadar.preflight/v1")
            self.assertEqual(data["summary"]["total"], 1)


if __name__ == "__main__":
    unittest.main()
