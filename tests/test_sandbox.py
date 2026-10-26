"""The test sandbox: writable candidate, no home, no network, read-only Git."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from swarm import sandbox


@unittest.skipUnless(sandbox.available(), "bubblewrap must be installed and usable")
class SandboxTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main", cwd=self.repo)
        (self.repo / "value.py").write_text("value = 1\n")
        self.git("add", ".", cwd=self.repo)
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "-qm", "fixture", cwd=self.repo)
        self.candidate = self.root / "candidate"
        self.git("worktree", "add", "--detach", str(self.candidate), "HEAD",
                 cwd=self.repo)

    def git(self, *args, cwd):
        result = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                                text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def run_in_sandbox(self, code, *, network=False):
        argv = sandbox.wrap(self.candidate, [sys.executable, "-c", code],
                            repo_root=self.repo, network=network)
        return subprocess.run(argv, capture_output=True, text=True, timeout=30)

    def test_candidate_is_writable_home_is_empty_and_keys_are_absent(self):
        code = ("import os,pathlib;"
                "pathlib.Path('new.txt').write_text('written');"
                "print(pathlib.Path.home());"
                "print(pathlib.Path('new.txt').is_file());"
                "print(os.environ.get('DEEPSEEK_API_KEY'))")
        result = self.run_in_sandbox(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ["/tmp/home", "True", "None"])

    def test_git_metadata_is_readable_and_read_only(self):
        code = ("import pathlib,subprocess;"
                "print(subprocess.run(['git','rev-parse','--short','HEAD'],"
                "capture_output=True,text=True).stdout.strip());"
                "print(pathlib.Path('.git').is_file())")
        result = self.run_in_sandbox(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.split()
        self.assertEqual(len(lines[0]), 7)
        self.assertEqual(lines[1], "True")
        marker = self.candidate / ".git"
        before = marker.read_text()
        code = "import pathlib;pathlib.Path('.git').write_text('broken')"
        result = self.run_in_sandbox(code)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_text(), before)

    def test_network_is_unavailable_by_default(self):
        code = ("import socket;s=socket.socket();s.settimeout(1)\n"
                "try:\n s.connect(('1.1.1.1',53));print('connected')\n"
                "except OSError:\n print('blocked')")
        result = self.run_in_sandbox(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("blocked", result.stdout)

    def test_missing_sandbox_fails_closed(self):
        with mock.patch.object(sandbox, "available", return_value=False):
            with self.assertRaises(sandbox.SandboxUnavailable):
                sandbox.wrap(self.candidate, ["true"], repo_root=self.repo)


if __name__ == "__main__":
    unittest.main()
