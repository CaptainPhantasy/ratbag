import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from swarm import gitops


def fixture_repo(expected=2, extra_test=""):
    """Fixtures are retained in /tmp; verification never deletes worktrees."""
    root = Path(tempfile.mkdtemp(prefix="swarm-engine-tests-"))
    repo = root / "repository"
    repo.mkdir()
    gitops.git(repo, "init")
    gitops.git(repo, "config", "user.name", "Offline test fixture")
    gitops.git(repo, "config", "user.email", "fixture@localhost")
    (repo / ".gitignore").write_text("__pycache__/\n.env*\nignored.txt\n")
    (repo / "app.py").write_text("def value():\n    return 1\n")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_value.py").write_text("import unittest\nfrom app import value\n\nclass ValueTests(unittest.TestCase):\n    def test_value(self):\n        self.assertEqual(value(), " + str(expected) + ")\n" + extra_test)
    gitops.git(repo, "add", "-A")
    gitops.git(repo, "commit", "-m", "Initial local fixture")
    return root, repo


def value_patch(old=1, new=2):
    return f"diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1,2 +1,2 @@\n def value():\n-    return {old}\n+    return {new}\n"


class GitOperationsTests(unittest.TestCase):
    def test_snapshot_preserves_dirty_and_untracked_without_touching_checkout(self):
        root, repo = fixture_repo()
        (repo / "app.py").write_text("def value():\n    return 3\n")
        (repo / "helper.py").write_text("answer = 42\n")
        (repo / ".env").write_text("fixture only\n")
        (repo / "ignored.txt").write_text("not source\n")
        before = gitops.git(repo, "status", "--porcelain=v1", "-z")
        index_before = (repo / ".git" / "index").read_bytes()
        result = gitops.create_snapshot(repo, root / "snapshot")
        snapshot = Path(result["snapshot_path"])
        self.assertEqual((snapshot / "app.py").read_text(), (repo / "app.py").read_text())
        self.assertEqual((snapshot / "helper.py").read_text(), "answer = 42\n")
        self.assertFalse((snapshot / ".env").exists())
        self.assertFalse((snapshot / "ignored.txt").exists())
        self.assertEqual(gitops.git(repo, "status", "--porcelain=v1", "-z"), before)
        self.assertEqual((repo / ".git" / "index").read_bytes(), index_before)
        self.assertNotEqual(result["base_commit"], result["snapshot_commit"])
        self.assertIn("helper.py", result["baseline_patch"])

    def test_removed_working_file_is_retained_in_snapshot_quarantine(self):
        root, repo = fixture_repo()
        os.replace(repo / "app.py", root / "owner-removed.quarantine")
        result = gitops.create_snapshot(repo, root / "snapshot")
        self.assertFalse((Path(result["snapshot_path"]) / "app.py").exists())
        self.assertTrue((root / "snapshot-removed.quarantine" / "app.py").exists())
        self.assertTrue((root / "owner-removed.quarantine").exists())

    def test_candidate_patch_and_workspace_survive(self):
        root, repo = fixture_repo()
        result = gitops.create_snapshot(repo, root / "snapshot")
        candidate = gitops.make_candidate(Path(result["snapshot_path"]), result["snapshot_commit"], root / "candidate", value_patch())
        self.assertEqual((root / "candidate" / "app.py").read_text(), "def value():\n    return 2\n")
        self.assertEqual((repo / "app.py").read_text(), "def value():\n    return 1\n")
        self.assertEqual(candidate["patch_hash"], hashlib.sha256(candidate["patch"].encode()).hexdigest())
        self.assertEqual(candidate["candidate_hash"], gitops.working_identity(root / "candidate"))
        self.assertTrue((root / "candidate").is_dir())

    def test_patch_transport_newline_preserves_source_eof_markers(self):
        marker = "\\ No newline at end of file\n"
        for old_newline, new_newline in ((True, True), (True, False), (False, True), (False, False)):
            for missing_transport in (False, True):
                with self.subTest(old_newline=old_newline, new_newline=new_newline, missing_transport=missing_transport):
                    root, repo = fixture_repo()
                    original = b"def value():\n    return 1" + (b"\n" if old_newline else b"")
                    expected = b"def value():\n    return 2" + (b"\n" if new_newline else b"")
                    (repo / "app.py").write_bytes(original)
                    snapshot = gitops.create_snapshot(repo, root / "snapshot")
                    patch = "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1,2 +1,2 @@\n def value():\n-    return 1\n"
                    patch += "" if old_newline else marker
                    patch += "+    return 2\n" + ("" if new_newline else marker)
                    if missing_transport:
                        patch = patch[:-1]
                    candidate = gitops.make_candidate(Path(snapshot["snapshot_path"]), snapshot["snapshot_commit"], root / "candidate", patch)
                    self.assertEqual((root / "candidate" / "app.py").read_bytes(), expected)
                    self.assertEqual((repo / "app.py").read_bytes(), original)
                    self.assertEqual(candidate["transport_newline_added"], missing_transport)
                    self.assertEqual(candidate["patch"].count(marker), int(not old_newline) + int(not new_newline))
                    canonical = gitops.git(root / "candidate", "diff", "--cached", "--full-index", "--binary", snapshot["snapshot_commit"])
                    self.assertEqual(candidate["patch"].encode(), canonical)
                    self.assertEqual(candidate["patch_hash"], hashlib.sha256(canonical).hexdigest())

    def test_missing_transport_newline_does_not_repair_incomplete_or_wrong_hunks(self):
        for patch in (value_patch().replace("@@ -1,2 +1,2 @@", "@@ -1,3 +1,3 @@"), value_patch(old=99)):
            with self.subTest(patch=patch):
                root, repo = fixture_repo()
                snapshot = gitops.create_snapshot(repo, root / "snapshot")
                with self.assertRaises(gitops.GitError):
                    gitops.make_candidate(Path(snapshot["snapshot_path"]), snapshot["snapshot_commit"], root / "invalid-candidate", patch[:-1])
                self.assertEqual((repo / "app.py").read_bytes(), b"def value():\n    return 1\n")

    def test_bad_patch_application_retains_workspace(self):
        root, repo = fixture_repo()
        result = gitops.create_snapshot(repo, root / "snapshot")
        with self.assertRaises(gitops.GitError):
            gitops.make_candidate(Path(result["snapshot_path"]), result["snapshot_commit"], root / "bad-candidate", value_patch(old=99))
        self.assertTrue((root / "bad-candidate").is_dir())
        self.assertEqual((repo / "app.py").read_text(), "def value():\n    return 1\n")

    def test_context_omits_symlinks_and_possible_credentials(self):
        root, repo = fixture_repo()
        outside = root / "outside.txt"
        outside.write_text("private outside content")
        (repo / "linked.py").symlink_to(outside)
        (repo / "settings.py").write_text('api_key = "' + "fixture_credential_value" + '"\n')
        (repo / "safe.py").write_text("safe_value = 100\n")
        context = gitops.inspect_source(repo, "inspect source", "value")
        self.assertNotIn("private outside content", context["source"])
        self.assertNotIn("fixture_credential_value", context["source"])
        self.assertIn("safe_value = 100", context["source"])
        matches = gitops.source_matches(repo, "private")
        self.assertNotIn("private outside content", matches)

    def test_shell_and_install_forms_rejected(self):
        for command in ("pytest && echo done", "pytest | tee log", "bash -c pytest", "npx vitest run", "npm install", "pytest $(pwd)", "X=1 pytest"):
            with self.subTest(command=command), self.assertRaises(gitops.GitError):
                gitops.parse_test_command(command)
        self.assertEqual(gitops.parse_test_command('python3 -m unittest discover -s "tests with spaces"'), ["python3", "-m", "unittest", "discover", "-s", "tests with spaces"])

    def test_project_declared_command_wins_over_package_guess(self):
        root, repo = fixture_repo()
        (repo / "package.json").write_text(json.dumps({"scripts": {"test": "jest --runInBand"}}))
        args, reason = gitops.discover_test_command(repo)
        self.assertEqual(args, ["npm", "test"])
        self.assertIn("declared", reason)

    def test_unsafe_paths_and_model_shell_commands_rejected(self):
        root, repo = fixture_repo()
        for path in ("../outside.py", "/tmp/outside.py", ".env", ".git/config", "credentials.json"):
            self.assertFalse(gitops.safe_name(path))
        for args in (["python3", "-c", "print('not a suite')"], ["sh", "-c", "pytest"], ["curl", "https://example.invalid"]):
            with self.assertRaises(gitops.GitError):
                gitops.validate_suggested_command(repo, args)
        self.assertEqual(gitops.validate_suggested_command(repo, ["python3", "-m", "unittest", "discover"]), ["python3", "-m", "unittest", "discover"])


if __name__ == "__main__":
    unittest.main()
