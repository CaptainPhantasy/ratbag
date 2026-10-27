"""Publishing puts one branch on the remote and never rewrites anything."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from swarm.handoff import HandoffError, publish


def git(*args, cwd=None):
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd)


class HandoffTests(unittest.TestCase):
    def test_publish_commits_and_pushes_the_preview_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            remote = Path(tmp) / "remote.git"
            workspace = Path(tmp) / "work"
            workspace.mkdir()
            (workspace / "index.html").write_text("<h1>hello</h1>", encoding="utf-8")
            self.assertEqual(git("init", "--bare", str(remote)).returncode, 0)

            result = publish(workspace, remote=str(remote), branch="preview", message="feat: hello")

            self.assertTrue(result.pushed)
            self.assertEqual(result.branch, "preview")
            self.assertTrue((workspace / ".gitignore").is_file())
            branch = git("rev-parse", "preview", cwd=remote)
            self.assertEqual(branch.stdout.strip(), result.commit)

    def test_publish_without_a_remote_commits_locally_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "work"
            workspace.mkdir()
            (workspace / "note.txt").write_text("hello", encoding="utf-8")

            result = publish(workspace)

            self.assertFalse(result.pushed)
            self.assertEqual(result.remote, "")
            self.assertTrue(result.commit)
            self.assertEqual(git("rev-parse", "HEAD", cwd=workspace).stdout.strip(), result.commit)

    def test_a_second_publish_adds_a_commit_rather_than_rewriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "work"
            workspace.mkdir()
            (workspace / "note.txt").write_text("first", encoding="utf-8")
            first = publish(workspace)
            (workspace / "note.txt").write_text("second", encoding="utf-8")
            second = publish(workspace)

            self.assertNotEqual(first.commit, second.commit)
            log = git("log", "--oneline", cwd=workspace).stdout.strip().splitlines()
            self.assertEqual(len(log), 2)

    def test_a_missing_workspace_is_refused(self):
        with self.assertRaises(HandoffError):
            publish("/tmp/ratbag-workspace-that-does-not-exist", remote="")


if __name__ == "__main__":
    unittest.main()
