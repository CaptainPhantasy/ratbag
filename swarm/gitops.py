"""Retained Git candidates and bounded, source-grounded repository inspection."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


MAX_PATCH_BYTES = 128_000
MAX_OVERLAY_BYTES = 32_000_000
MAX_OVERLAY_FILE_BYTES = 4_000_000
SECRET_PARTS = {".git", ".aws", ".ssh", ".gnupg", ".swarm-data", "node_modules", "__pycache__", ".venv", "venv"}
SECRET_NAMES = {".npmrc", ".pypirc", ".netrc", "credentials", "credentials.json", "secrets.json", "secrets.yaml", "secrets.yml", "id_rsa", "id_ed25519"}
SECRET_ASSIGNMENT = re.compile(r"(?im)(?:api[_-]?key|access[_-]?token|secret[_-]?key|private[_-]?key|password)\s*[:=]\s*['\"]([^'\"\n]{12,})['\"]")
SECRET_TOKEN = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16})\b")


def contains_secret(text: str) -> bool:
    return bool(SECRET_ASSIGNMENT.search(text) or SECRET_TOKEN.search(text) or "-----BEGIN PRIVATE KEY-----" in text)


def minimal_env() -> dict[str, str]:
    """Inherit executable lookup and locale, never arbitrary environment secrets."""
    env = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "SYSTEMROOT", "WINDIR", "PATHEXT") if key in os.environ}
    env.setdefault("PATH", os.defpath)
    env.update({"CI": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1", "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
    return env


def git(repo: Path, *args: str, data: bytes | None = None, timeout: float = 60) -> bytes:
    executable = shutil.which("git")
    if not executable:
        raise GitError("Git is not installed or is not on PATH.")
    result = subprocess.run([executable, "-C", str(repo), "-c", "core.hooksPath=" + os.devnull, "-c", "core.fsmonitor=false", *args], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=minimal_env(), timeout=timeout, shell=False, close_fds=True)
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise GitError(f"Git {args[0] if args else 'command'} failed: {detail[:3000]}")
    return result.stdout


def repository_root(repo: Path) -> Path:
    repo = repo.expanduser().resolve(strict=True)
    root = Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if repo != root:
        raise GitError("Choose the repository's top-level directory so the snapshot has one unambiguous root.")
    git(root, "rev-parse", "--verify", "HEAD^{commit}")
    return root


def safe_name(name: str) -> bool:
    path = Path(name)
    lower = [part.lower() for part in path.parts]
    if not name or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return False
    if any(part in SECRET_PARTS for part in lower):
        return False
    leaf = lower[-1]
    return not (leaf in SECRET_NAMES or leaf.startswith(".env") or leaf.endswith((".pem", ".key", ".p12", ".pfx", ".keystore")))


def inside_file(root: Path, name: str) -> Path:
    if not safe_name(name):
        raise GitError(f"The path is outside the permitted source set: {name}")
    path = root / name
    for parent in (path, *path.parents):
        if parent == root:
            break
        if parent.is_symlink():
            raise GitError(f"Symlink paths are not read or patched: {name}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise GitError(f"The path leaves the repository: {name}")
    return path


def _names(raw: bytes) -> list[str]:
    return [part.decode("utf-8", "surrogateescape") for part in raw.split(b"\0") if part]


def source_names(repo: Path) -> list[str]:
    names = _names(git(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard"))
    ignored = set(_names(git(repo, "ls-files", "-z", "--cached", "--ignored", "--exclude-standard")))
    return sorted({name for name in names if safe_name(name) and name not in ignored})


def _overlay(repo: Path) -> tuple[dict[str, bytes | None], list[str]]:
    changed = _names(git(repo, "diff", "HEAD", "--name-only", "-z"))
    untracked = _names(git(repo, "ls-files", "--others", "--exclude-standard", "-z"))
    values: dict[str, bytes | None] = {}
    omitted = []
    total = 0
    for name in sorted(set(changed + untracked)):
        if not safe_name(name):
            omitted.append(name)
            continue
        try:
            path = inside_file(repo, name)
        except GitError:
            omitted.append(name)
            continue
        if path.exists() and not path.is_file():
            omitted.append(name)
            continue
        if path.exists() and path.stat().st_size > MAX_OVERLAY_FILE_BYTES:
            raise GitError(f"The changed source file {name} exceeds the 4 MB snapshot limit. Choose a smaller source change before retrying.")
        content = path.read_bytes() if path.exists() else None
        if content and b"\x00" not in content and contains_secret(content.decode("utf-8", "replace")):
            omitted.append(name)
            continue
        total += len(content or b"")
        if total > MAX_OVERLAY_BYTES:
            raise GitError("Changed and untracked source exceeds the 32 MB snapshot limit. Reduce the selected repository changes before retrying.")
        values[name] = content
    return values, omitted


def create_snapshot(repo: Path, destination: Path) -> dict:
    """Snapshot safe working files without modifying the owner's checkout or index."""
    root = repository_root(repo)
    base = git(root, "rev-parse", "HEAD").decode().strip()
    overlay, omitted = _overlay(root)
    destination = destination.resolve()
    if destination.exists():
        raise GitError("The snapshot destination already exists; the prior workspace has been retained.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    git(root, "worktree", "add", "--detach", str(destination), base)
    for name, content in overlay.items():
        target = inside_file(destination, name)
        if content is None:
            if target.exists():
                retained = destination.parent / "snapshot-removed.quarantine" / name
                retained.parent.mkdir(parents=True, exist_ok=True)
                os.replace(target, retained)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        original = inside_file(root, name)
        if original.exists():
            target.chmod(original.stat().st_mode & 0o777)
    overlay_after, omitted_after = _overlay(root)
    if git(root, "rev-parse", "HEAD").decode().strip() != base or overlay != overlay_after or omitted != omitted_after:
        raise GitError("Repository files changed while the snapshot was being made. The partial snapshot is retained; resume after editing stops.")
    git(destination, "add", "-A", "--", ".")
    tree = git(destination, "write-tree").decode().strip()
    env = minimal_env()
    env.update({"GIT_AUTHOR_NAME": "Swarm snapshot", "GIT_AUTHOR_EMAIL": "snapshot@localhost", "GIT_COMMITTER_NAME": "Swarm snapshot", "GIT_COMMITTER_EMAIL": "snapshot@localhost"})
    proc = subprocess.run([shutil.which("git") or "git", "-C", str(destination), "-c", "core.hooksPath=" + os.devnull, "commit-tree", tree, "-p", base], env=env, input=b"Retained source snapshot for Swarm Control\n", stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False, timeout=60, close_fds=True)
    if proc.returncode:
        raise GitError("Git could not preserve the source snapshot commit.")
    snapshot = proc.stdout.decode().strip()
    git(destination, "update-ref", "--no-deref", "HEAD", snapshot)
    baseline = git(destination, "diff", "--full-index", "--binary", base, snapshot).decode("utf-8", "replace")
    return {"repo_path": str(root), "base_commit": base, "snapshot_commit": snapshot, "snapshot_path": str(destination), "snapshot_overlay_files": sorted(overlay), "omitted_source_paths": omitted, "baseline_patch": baseline}


def working_identity(repo: Path) -> str:
    digest = hashlib.sha256()
    for name in sorted(_names(git(repo, "ls-files", "-z"))):
        path = repo / name
        digest.update(name.encode("utf-8", "surrogateescape") + b"\0")
        if path.is_symlink():
            digest.update(b"link\0" + os.readlink(path).encode())
        elif path.is_file():
            digest.update(str(path.stat().st_mode & 0o777).encode() + b"\0")
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(65536), b""):
                    digest.update(block)
        elif not path.exists():
            digest.update(b"missing")
        else:
            digest.update(b"non-file")
        digest.update(b"\0")
    return digest.hexdigest()


def make_candidate(snapshot: Path, snapshot_commit: str, destination: Path, patch: str) -> dict:
    if not patch.startswith("diff --git ") or not patch.strip():
        raise GitError("The builder did not return a nonempty unified Git patch.")
    # A diff needs a final transport LF even when its last source line has none.
    # Git's explicit "\\ No newline at end of file" markers retain that meaning.
    # Never trim or reconstruct hunk contents; Git still validates every hunk.
    transport_newline_added = not patch.endswith("\n")
    raw = (patch + ("\n" if transport_newline_added else "")).encode("utf-8")
    if len(raw) > MAX_PATCH_BYTES:
        raise GitError("The proposed patch exceeds the 128 KB full-review limit. Split the task into a smaller change.")
    if contains_secret(patch):
        raise GitError("The proposed patch contains a possible credential. Remove private credential material before continuing.")
    if re.search(r"(?m)^(deleted file mode|rename from|rename to|copy from|copy to|GIT binary patch|Binary files |new mode 120000|new file mode 120000|new file mode 160000)", patch):
        raise GitError("This runner accepts text additions and edits only; deleting, moving, binary, symlink, or submodule changes require a separate review.")
    numstat = git(snapshot, "apply", "--numstat", "-z", "-", data=raw)
    for entry in numstat.split(b"\0"):
        if not entry:
            continue
        parts = entry.split(b"\t", 2)
        if len(parts) != 3 or parts[0] == b"-" or parts[1] == b"-":
            raise GitError("A proposed patch entry is not a supported text file.")
        inside_file(snapshot, parts[2].decode("utf-8", "surrogateescape"))
    if destination.exists():
        raise GitError("The candidate workspace already exists and has been retained.")
    git(snapshot, "worktree", "add", "--detach", str(destination), snapshot_commit)
    git(destination, "apply", "--check", "--index", "-", data=raw)
    git(destination, "apply", "--index", "-", data=raw)
    canonical = git(destination, "diff", "--cached", "--full-index", "--binary", snapshot_commit).decode("utf-8", "replace")
    if not canonical.strip() or len(canonical.encode()) > MAX_PATCH_BYTES:
        raise GitError("The resulting patch is empty or exceeds the full-review limit.")
    return {"candidate_path": str(destination), "candidate_hash": working_identity(destination), "patch": canonical, "patch_hash": hashlib.sha256(canonical.encode()).hexdigest(), "transport_newline_added": transport_newline_added}


def inspect_source(repo: Path, task: str, symbol: str, preferred: str = "", limit: int = 80_000) -> dict:
    names = source_names(repo)
    terms = {term.lower() for term in re.findall(r"[A-Za-z_][A-Za-z_0-9]{2,}", task + " " + symbol)}
    def score(name: str) -> tuple[int, str]:
        value = 30 if name in preferred else 0
        value += sum(3 for term in terms if term in name.lower())
        if Path(name).suffix in {".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go", ".json", ".toml"}:
            value += 2
        return -value, name
    chunks, selected, omitted = [], [], []
    used = 0
    for name in sorted(names, key=score):
        if len(selected) >= 14:
            break
        try:
            path = inside_file(repo, name)
            if not path.is_file():
                continue
            if path.stat().st_size > 60_000:
                omitted.append({"path": name, "reason": "source file exceeds the 60 KB per-file context limit"})
                continue
            raw = path.read_bytes()
            if b"\x00" in raw:
                continue
            content = raw.decode("utf-8")
            if contains_secret(content):
                omitted.append({"path": name, "reason": "possible credential assignment"})
                continue
        except (UnicodeDecodeError, GitError, OSError):
            continue
        block = f"FILE: {name}\nSHA256: {hashlib.sha256(raw).hexdigest()}\nFULL SOURCE ({len(content)} characters):\n{content}\nEND FILE: {name}\n"
        if used + len(block.encode("utf-8")) + 1 > limit:
            omitted.append({"path": name, "reason": "source context budget"})
            continue
        chunks.append(block)
        selected.append(name)
        used += len(block.encode("utf-8")) + 1
    if not selected:
        raise GitError("No readable source files fit the safe context limits. Select a repository containing text source files.")
    source = "\n".join(chunks)
    return {"files": names, "selected_files": selected, "omitted_files": omitted, "source": source, "source_characters": len(source), "source_bytes": len(source.encode("utf-8")), "file_count": len(names)}


def source_matches(repo: Path, symbol: str, max_chars: int = 12_000) -> str:
    if not symbol.strip():
        return "No symbol filter supplied."
    matches, used = [], 0
    for name in source_names(repo):
        try:
            path = inside_file(repo, name)
            if not path.is_file() or path.stat().st_size > 200_000:
                continue
            content = path.read_text(encoding="utf-8")
            if contains_secret(content):
                continue
        except (GitError, UnicodeError, OSError):
            continue
        for number, line in enumerate(content.splitlines(), 1):
            if symbol not in line:
                continue
            entry = f"{name}:{number}: {line}"
            if used + len(entry) > max_chars:
                return "\n".join(matches) + "\n[Further matching lines omitted at the measured character limit.]"
            matches.append(entry)
            used += len(entry) + 1
    return "\n".join(matches) or "No literal matches found in the safe source set."


def parse_test_command(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        args = list(value)
    else:
        if "\n" in value or "\r" in value:
            raise GitError("Enter one test command without line breaks.")
        lexer = shlex.shlex(value, posix=True, punctuation_chars=";&|<>")
        lexer.whitespace_split = True
        lexer.commenters = ""
        args = list(lexer)
    if not args or len(args) > 80 or any(not isinstance(arg, str) or not arg or "\x00" in arg or len(arg) > 4000 for arg in args):
        raise GitError("Enter a valid executable and its arguments for the test command.")
    if any(re.fullmatch(r"[;&|<>]+", arg) or "$(" in arg or "`" in arg for arg in args):
        raise GitError("Shell operators and substitutions are unsupported. Enter a single executable with arguments.")
    command = Path(args[0]).name.lower()
    if command in {"sh", "bash", "zsh", "fish", "dash", "ksh", "cmd", "cmd.exe", "powershell", "pwsh", "env", "sudo", "su"}:
        raise GitError("Shell and privilege-wrapper commands are unsupported. Choose the test runner itself.")
    if re.match(r"^[A-Za-z_][A-Za-z_0-9]*=", args[0]):
        raise GitError("Environment assignments are unsupported in the test command.")
    if command in {"npx", "bunx", "curl", "wget"} or (command in {"npm", "pnpm", "yarn", "bun"} and any(arg in {"install", "add", "exec", "dlx", "create"} for arg in args[1:])):
        raise GitError("Install/download commands are not test commands. Prepare dependencies separately and select an installed test runner.")
    return args


def discover_test_command(repo: Path) -> tuple[list[str] | None, str]:
    package = repo / "package.json"
    if package.is_file():
        try:
            data = json.loads(package.read_text())
            script = data.get("scripts", {}).get("test", "")
            if isinstance(script, str) and script.strip() and "no test specified" not in script.lower():
                manager = "pnpm" if (repo / "pnpm-lock.yaml").exists() else "yarn" if (repo / "yarn.lock").exists() else "npm"
                return [manager, "test"], "Selected the test script declared in package.json."
        except (ValueError, OSError):
            pass
    if (repo / "Cargo.toml").is_file():
        return ["cargo", "test"], "Selected the test runner declared by Cargo.toml."
    pytest = repo / "pytest.ini"
    pyproject = repo / "pyproject.toml"
    if pytest.exists() or (pyproject.is_file() and "[tool.pytest" in pyproject.read_text()):
        return ["python3", "-m", "pytest", "-q"], "Selected the configured pytest suite."
    test_files = [path for path in (repo / "tests").glob("test*.py") if path.is_file()] if (repo / "tests").is_dir() else []
    if any("unittest" in path.read_text(errors="replace") for path in test_files[:40]):
        return ["python3", "-m", "unittest", "discover", "-s", "tests", "-v"], "Selected the unittest suite found in tests/."
    return None, "No declared test command was found; a test command is needed."


def validate_suggested_command(repo: Path, value: list[str]) -> list[str]:
    args = parse_test_command(value)
    command = Path(args[0]).name.lower()
    allowed = command in {"pytest", "vitest", "jest"} and len(args) >= 1
    allowed |= command == "cargo" and len(args) > 1 and args[1] == "test"
    allowed |= command in {"python", "python3"} and len(args) > 2 and args[1] == "-m" and args[2] in {"pytest", "unittest"}
    allowed |= command in {"npm", "pnpm", "yarn"} and args[1:] in (["test"], ["run", "test"])
    allowed |= command == "node" and "--test" in args[1:] and not any(arg in {"-e", "--eval"} for arg in args[1:])
    if not allowed:
        raise GitError("The suggested command is outside the supported test-runner forms. Enter the command explicitly after reviewing it.")
    return args
