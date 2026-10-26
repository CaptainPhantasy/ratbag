"""Bounded project discovery and source-grounded check choices for the workbench."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import threading
import uuid

from . import gitops


MAX_DIRECTORIES = 512
MAX_PROJECTS = 100
MAX_DEPTH = 2
MAX_MANIFEST_BYTES = 256_000
SKIP_DIRECTORIES = {"node_modules", "vendor", "venv", "__pycache__", "dist", "build", "target", "runs", "artifacts"}
SAMPLE_TASK = (
    "Update normalize_label to trim surrounding whitespace and collapse every run of whitespace, "
    "including tabs and newlines, to one ASCII space. Preserve letter case. Return an empty string "
    "for whitespace-only input and keep raising TypeError for non-string input. Add focused tests."
)


def _project_id(path: Path) -> str:
    return "p_" + hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:16]


def _read(path: Path) -> str:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return ""


def test_options(repo: Path) -> list[dict]:
    """Describe checks declared by source; discovery never executes project code."""
    options = []

    def add(label: str, args: list[str], reason: str):
        gitops.parse_test_command(args)
        command = shlex.join(args)
        if command not in {option["command"] for option in options}:
            options.append({"id": "t_" + hashlib.sha256(command.encode()).hexdigest()[:12],
                            "label": label, "command": command, "reason": reason})

    try:
        package = json.loads(_read(repo / "package.json") or "{}")
    except (ValueError, OSError):
        package = {}
    scripts = package.get("scripts", {}) if isinstance(package, dict) else {}
    if isinstance(scripts, dict):
        manager = "pnpm" if (repo / "pnpm-lock.yaml").is_file() else "yarn" if (repo / "yarn.lock").is_file() else "npm"
        for name in sorted(scripts, key=lambda key: (key != "test", key)):
            script = scripts[name]
            if not re.fullmatch(r"test(?::[A-Za-z0-9_-]{1,40})?", name):
                continue
            if not isinstance(script, str) or not script.strip() or "no test specified" in script.lower():
                continue
            # Test-watch scripts need an owner-supplied noninteractive command.
            if "watch" in name.lower() or re.search(r"(?:^|\s)--watch(?:\s|$)", script):
                continue
            args = [manager, "test"] if name == "test" else [manager, "run", name]
            add("Project test suite" if name == "test" else name.replace("test:", "Tests: ", 1), args,
                f"The {name} script is declared in package.json; existing project dependencies are required.")
    if (repo / "Cargo.toml").is_file() and not (repo / "Cargo.toml").is_symlink():
        add("Rust tests", ["cargo", "test"], "Cargo.toml declares a Rust project.")
    pyproject = _read(repo / "pyproject.toml")
    if _read(repo / "pytest.ini") or (repo / "pytest.ini").is_file() or "[tool.pytest" in pyproject:
        add("Python tests · pytest", ["python3", "-m", "pytest", "-q"], "A pytest configuration is present.")
    tests = repo / "tests"
    if tests.is_dir() and not tests.is_symlink():
        files = sorted(tests.glob("test*.py"))[:40]
        if any("unittest" in _read(path) for path in files):
            add("Python tests · unittest", ["python3", "-m", "unittest", "discover", "-s", "tests", "-v"],
                "The tests folder contains Python unittest tests.")
    root_tests = sorted(repo.glob("test*.py"))[:40]
    if any("unittest" in _read(path) for path in root_tests):
        add("Python tests · project root", ["python3", "-m", "unittest", "discover", "-v"],
            "The project root contains Python unittest tests.")
    return options


class ProjectCatalog:
    def __init__(self, data_dir: Path, roots: list[Path] | None = None):
        self.samples = Path(data_dir).resolve() / "projects"
        self._lock = threading.RLock()
        if roots is None:
            configured = [Path(value).expanduser() for value in os.getenv("SWARM_PROJECT_ROOTS", "").split(os.pathsep) if value.strip()]
            home = Path.home()
            defaults = [Path.cwd(), home / "Projects", home / "projects", home / "repos", home / "Code",
                        Path("/srv/projects"), Path("/opt/projects"), Path("/workspace/projects")]
            roots = configured + [path for path in defaults if path.is_dir()]
        # An explicit filesystem-root entry must never cause a filesystem-wide scan.
        self.roots = list(dict.fromkeys(path.expanduser().resolve() for path in [*roots, self.samples]
                                       if path.expanduser().resolve() != Path(path.anchor or "/")))

    def list(self) -> dict:
        found, visited = {}, set()
        inspected = 0
        limited = False
        for root in self.roots:
            if not root.is_dir():
                continue
            pending = [(root, 0)]
            while pending:
                path, depth = pending.pop(0)
                if path in visited:
                    continue
                visited.add(path)
                inspected += 1
                if inspected > MAX_DIRECTORIES or len(found) >= MAX_PROJECTS:
                    limited = True
                    break
                if (path / ".git").exists():
                    try:
                        actual = gitops.repository_root(path)
                    except (gitops.GitError, OSError):
                        continue
                    key = _project_id(actual)
                    found[key] = {"id": key, "name": actual.name, "path": str(actual),
                                  "kind": "sample" if actual.is_relative_to(self.samples) else "project"}
                    # Nested dependencies and nested repos are not scanned inside an existing project.
                    continue
                if depth >= MAX_DEPTH:
                    continue
                try:
                    entries = []
                    with os.scandir(path) as scan:
                        for entry_number, entry in enumerate(scan):
                            if entry_number >= MAX_DIRECTORIES:
                                limited = True
                                break
                            if (entry.name.startswith(".") or entry.name in SKIP_DIRECTORIES or
                                    entry.name.endswith(".quarantine") or entry.is_symlink()):
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                entries.append(Path(entry.path))
                    pending.extend((child, depth + 1) for child in sorted(entries))
                except (PermissionError, FileNotFoundError):
                    continue
            if inspected > MAX_DIRECTORIES or len(found) >= MAX_PROJECTS:
                break
        return {"projects": sorted(found.values(), key=lambda item: (item["name"].lower(), item["path"])),
                "roots": [{"path": str(path), "available": path.is_dir()} for path in self.roots],
                "limited": limited, "limits": {"depth": MAX_DEPTH, "directories": MAX_DIRECTORIES, "projects": MAX_PROJECTS}}

    def inspect(self, project_id: str) -> dict:
        if not isinstance(project_id, str) or not re.fullmatch(r"p_[a-f0-9]{16}", project_id):
            raise ValueError("Choose a project from the list.")
        project = next((item for item in self.list()["projects"] if item["id"] == project_id), None)
        if project is None:
            raise ValueError("That project is no longer available. Refresh the project list.")
        return self.inspect_path(Path(project["path"]), project)

    def inspect_path(self, path: Path, project: dict | None = None) -> dict:
        root = gitops.repository_root(path)
        options = test_options(root)
        branch = gitops.git(root, "rev-parse", "--abbrev-ref", "HEAD", timeout=10).decode().strip()
        project = dict(project or {"id": _project_id(root), "name": root.name, "path": str(root), "kind": "project"})
        project.update(branch=branch, test_options=options,
                       recommended_test_id=options[0]["id"] if options else None,
                       notes=["These choices come from project files. They have not been run during discovery."] if options else
                             ["No declared test suite was found. Enter a check command in Advanced options."])
        return project

    def create_sample(self) -> dict:
        with self._lock:
            self.samples.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Reopen the retained tutorial project; never overwrite owner edits.
            existing = self.samples / "label-workshop"
            project = None
            if existing.is_dir() and (existing / ".git").exists():
                try:
                    project = self.inspect_path(existing)
                except (gitops.GitError, OSError):
                    pass  # Keep a partial earlier attempt; create a fresh named sample.
            if project is None:
                destination = existing if not existing.exists() else self.samples / ("label-workshop-" + uuid.uuid4().hex[:8])
                destination.mkdir(mode=0o700)
                (destination / "tests").mkdir()
                (destination / "labels.py").write_text(
                    '"""A small, real project for your first Swarm task."""\n\n'
                    'def normalize_label(value):\n'
                    '    if not isinstance(value, str):\n'
                    '        raise TypeError("value must be a string")\n'
                    '    return value.strip()\n', encoding="utf-8")
                (destination / "tests" / "test_labels.py").write_text(
                    'import unittest\nfrom labels import normalize_label\n\n'
                    'class LabelTests(unittest.TestCase):\n'
                    '    def test_trim(self):\n        self.assertEqual(normalize_label("  Example  "), "Example")\n'
                    '    def test_empty(self):\n        self.assertEqual(normalize_label("   "), "")\n'
                    '    def test_type(self):\n        with self.assertRaises(TypeError):\n            normalize_label(None)\n', encoding="utf-8")
                (destination / "README.md").write_text(
                    '# Label workshop\n\nA safe first task for Swarm Control.\n\n'
                    'The task is to collapse repeated whitespace while preserving the current behavior.\n\n'
                    'Run the current checks with `python3 -m unittest discover -s tests -v`.\n'
                    'The app makes a separate candidate and preserves these original files.\n', encoding="utf-8")
                (destination / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
                gitops.git(destination, "init", "--initial-branch=main", timeout=15)
                gitops.git(destination, "add", "--", "labels.py", "tests/test_labels.py", "README.md", ".gitignore", timeout=15)
                gitops.git(destination, "-c", "user.name=Swarm workshop", "-c", "user.email=workshop@localhost",
                           "-c", "commit.gpgsign=false", "commit", "-m", "Start the label workshop", timeout=15)
                project = self.inspect_path(destination)
            project["kind"] = "sample"
            return {"project": project, "suggested_task": {"task": SAMPLE_TASK, "symbol": "normalize_label",
                                                             "test_choice": project["recommended_test_id"]}}
