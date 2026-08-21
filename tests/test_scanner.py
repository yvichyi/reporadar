"""Tests for reporadar's scanner, report, and CLI.

Run with:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from reporadar.cli import main  # noqa: E402
from reporadar.model import RepoStatus  # noqa: E402
from reporadar.report import relative_time, render  # noqa: E402
from reporadar.scanner import find_repos, inspect_repo, scan  # noqa: E402


def sh(*args: str, cwd: Path | None = None) -> str:
    proc = subprocess.run(
        args, cwd=str(cwd) if cwd else None,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise AssertionError(f"{' '.join(args)} failed:\n{proc.stderr}")
    return proc.stdout


def make_commit(repo: Path, fname: str, content: str = "hello\n") -> None:
    (repo / fname).write_text(content, encoding="utf-8")
    sh("git", "add", fname, cwd=repo)
    sh("git", "commit", "-m", f"add {fname}", cwd=repo)


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="reporadar-test-"))
        self.addCleanup(shutil_rmtree, self.tmp)

    def make_repo(self, name: str, with_commit: bool = True) -> Path:
        repo = self.tmp / name
        repo.mkdir(parents=True)
        sh("git", "init", "-b", "main", str(repo))
        sh("git", "config", "user.email", "test@example.com", cwd=repo)
        sh("git", "config", "user.name", "Test", cwd=repo)
        if with_commit:
            make_commit(repo, "README.md", f"# {name}\n")
        return repo


def shutil_rmtree(path: Path) -> None:
    import shutil
    shutil.rmtree(path, ignore_errors=True)


class TestFindRepos(Base):
    def test_finds_nested_repos(self) -> None:
        self.make_repo("projects/alpha")
        self.make_repo("projects/sub/beta")
        found = find_repos([self.tmp])
        names = {p.name for p in found}
        self.assertEqual(names, {"alpha", "beta"})

    def test_skips_junk_dirs(self) -> None:
        self.make_repo("code/real-project")
        self.make_repo("code/node_modules/fake-project")
        found = find_repos([self.tmp])
        self.assertEqual([p.name for p in found], ["real-project"])

    def test_depth_limit(self) -> None:
        self.make_repo("a/b/c/d/e/too-deep")
        self.assertEqual(find_repos([self.tmp], max_depth=3), [])
        self.assertEqual(len(find_repos([self.tmp], max_depth=6)), 1)

    def test_missing_root_is_ignored(self) -> None:
        self.assertEqual(find_repos([self.tmp / "nope"]), [])


class TestInspectRepo(Base):
    def test_clean_repo(self) -> None:
        repo = self.make_repo("clean")
        st = inspect_repo(repo)
        self.assertIsNone(st.error)
        self.assertEqual(st.branch, "main")
        self.assertFalse(st.is_dirty)
        self.assertEqual(st.changed, 0)
        self.assertIsNotNone(st.last_commit_ts)
        self.assertEqual(st.stashes, 0)

    def test_empty_repo_has_no_commits(self) -> None:
        repo = self.make_repo("fresh", with_commit=False)
        st = inspect_repo(repo)
        self.assertIsNone(st.last_commit_ts)
        self.assertFalse(st.is_dirty)

    def test_dirty_counts_untracked_and_modified(self) -> None:
        repo = self.make_repo("dirty")
        (repo / "new.txt").write_text("untracked", encoding="utf-8")
        (repo / "README.md").write_text("# changed\n", encoding="utf-8")
        st = inspect_repo(repo)
        self.assertEqual(st.changed, 2)
        self.assertTrue(st.is_dirty)

    def test_ahead_and_behind(self) -> None:
        origin = self.tmp / "origin.git"
        sh("git", "init", "--bare", "-b", "main", str(origin))
        repo = self.make_repo("cloned")
        sh("git", "remote", "add", "origin", str(origin), cwd=repo)
        sh("git", "push", "-u", "origin", "main", cwd=repo)

        make_commit(repo, "second.txt")
        st = inspect_repo(repo)
        self.assertTrue(st.has_upstream)
        self.assertEqual(st.ahead, 1)
        self.assertEqual(st.behind, 0)
        sh("git", "push", cwd=repo)

        # Simulate falling behind: move local main back one commit while
        # origin/main keeps the newest one.
        sh("git", "reset", "--hard", "HEAD~1", cwd=repo)
        st = inspect_repo(repo)
        self.assertEqual(st.ahead, 0)
        self.assertEqual(st.behind, 1)

    def test_stash_count(self) -> None:
        repo = self.make_repo("stasher")
        (repo / "wip.txt").write_text("wip", encoding="utf-8")
        sh("git", "add", "wip.txt", cwd=repo)
        sh("git", "stash", cwd=repo)
        st = inspect_repo(repo)
        self.assertEqual(st.stashes, 1)

    def test_detached_head(self) -> None:
        repo = self.make_repo("detached")
        sh("git", "checkout", "--detach", "HEAD", cwd=repo)
        st = inspect_repo(repo)
        self.assertEqual(st.branch, "(detached)")


class TestScan(Base):
    def test_scan_aggregates(self) -> None:
        self.make_repo("one")
        self.make_repo("two")
        results = scan([self.tmp])
        self.assertEqual({r.name for r in results}, {"one", "two"})
        self.assertTrue(all(isinstance(r, RepoStatus) for r in results))


class TestReport(unittest.TestCase):
    def test_relative_time(self) -> None:
        import time as _t
        now = 1_800_000_000.0
        self.assertEqual(relative_time(None), "no commits")
        self.assertEqual(relative_time(now - 30, now), "just now")
        self.assertEqual(relative_time(now - 300, now), "5m ago")
        self.assertEqual(relative_time(now - 7200, now), "2h ago")
        self.assertEqual(relative_time(now - 3 * 86400, now), "3d ago")
        self.assertEqual(relative_time(now - 90 * 86400, now), "3mo ago")
        _t.timezone  # silence linters; relative_time takes absolute epochs

    def test_render_plain_has_all_columns(self) -> None:
        repo = RepoStatus(path=Path("/tmp/demo"), branch="main", upstream="origin/main",
                          changed=3, ahead=2, stashes=1, last_commit_ts=1_800_000_000)
        text = render([repo], color=False)
        for header in ("REPO", "BRANCH", "STATUS", "SYNC", "LAST COMMIT", "STASH"):
            self.assertIn(header, text)
        self.assertIn("3 changes", text)
        self.assertIn("repos", text)

    def test_render_empty_conflict_wording(self) -> None:
        repo = RepoStatus(path=Path("/tmp/c"), conflicted=2)
        text = render([repo], color=False, ascii_only=True)
        self.assertIn("2 conflicts", text)


class TestCLI(Base):
    def run_cli(self, *argv: str) -> tuple[int, str]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main([str(self.tmp), *argv])
        return code, buf.getvalue()

    def test_table_output(self) -> None:
        self.make_repo("cli-repo")
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("cli-repo", out)
        self.assertIn("clean", out)

    def test_json_output(self) -> None:
        self.make_repo("json-repo")
        _code, out = self.run_cli("--json")
        data = json.loads(out)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "json-repo")
        self.assertIn("last_commit_ts", data[0])

    def test_dirty_filter(self) -> None:
        repo = self.make_repo("dirty-one")
        self.make_repo("clean-one")
        (repo / "x.txt").write_text("x", encoding="utf-8")
        _code, out = self.run_cli("--dirty")
        self.assertIn("dirty-one", out)
        self.assertNotIn("clean-one", out)

    def test_no_repos_exit_code(self) -> None:
        code, out = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn("No git repositories", out)


if __name__ == "__main__":
    unittest.main()
