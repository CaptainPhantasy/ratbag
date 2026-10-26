"""Run repository test commands in a bubblewrap sandbox.

The candidate checkout is writable. Everything else is read-only: the Python
toolchain, Git metadata for this checkout only, and the certificate files.
Other worktrees, the operator's home, the Swarm data directory, and the
network are not visible unless network access is explicitly enabled.
"""
from __future__ import annotations

import functools
import shutil
import subprocess
import sys
from pathlib import Path


class SandboxUnavailable(RuntimeError):
    pass


@functools.lru_cache(maxsize=1)
def available() -> bool:
    executable = shutil.which("bwrap")
    if not executable:
        return False
    try:
        result = subprocess.run(
            [executable, "--die-with-parent", "--unshare-all",
             "--ro-bind", "/", "/", "--", "/bin/true"],
            capture_output=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _git_mounts(root: Path, repo_root: Path | None) -> list[str]:
    marker = root / ".git"
    if marker.is_symlink():
        raise SandboxUnavailable("The checkout Git marker is a symbolic link; "
                                 "the test command was not run.")
    if marker.is_dir():
        return ["--ro-bind", str(marker), str(marker)]
    if not marker.is_file():
        return []
    text = marker.read_text(encoding="utf-8", errors="replace").strip()
    if not text.lower().startswith("gitdir:"):
        raise SandboxUnavailable("The checkout Git marker is not understood; "
                                 "the test command was not run.")
    pointer = text.split(":", 1)[1].strip()
    gitdir = Path(pointer)
    gitdir = (root / gitdir if not gitdir.is_absolute() else gitdir).resolve()
    allowed = (repo_root or root.parent).resolve()
    if not gitdir.is_relative_to(allowed) or not gitdir.is_dir():
        raise SandboxUnavailable("The checkout Git directory is outside the "
                                 "project; the test command was not run.")
    common = gitdir
    common_pointer = gitdir / "commondir"
    if common_pointer.is_symlink():
        raise SandboxUnavailable("The checkout Git common directory is a "
                                 "symbolic link; the test command was not run.")
    if common_pointer.is_file():
        target = Path(common_pointer.read_text(encoding="utf-8",
                                               errors="replace").strip())
        common = (gitdir / target if not target.is_absolute() else target).resolve()
    if not common.is_relative_to(allowed) or not common.is_dir():
        raise SandboxUnavailable("The checkout Git common directory is outside "
                                 "the project; the test command was not run.")
    mounts = ["--ro-bind", str(common), str(common)]
    worktrees = common / "worktrees"
    if worktrees.is_dir() and gitdir.is_relative_to(worktrees):
        # Hide sibling worktrees, then expose this checkout's own metadata.
        mounts += ["--tmpfs", str(worktrees), "--ro-bind", str(gitdir), str(gitdir)]
    mounts += ["--ro-bind", str(marker), str(marker)]
    return mounts


def wrap(root, argv: list[str], *, repo_root=None, network: bool = False) -> list[str]:
    """Return the bwrap argv for one test command. Fails closed."""
    executable = shutil.which("bwrap")
    if not executable or not available():
        raise SandboxUnavailable(
            "The isolated test runner is unavailable. Install bubblewrap; "
            "repository code was not run unconfined.")
    root = Path(root).resolve()
    command = [executable, "--die-with-parent", "--unshare-all"]
    if network:
        command.append("--share-net")

    real_python = Path(sys.executable).resolve()
    prefixes = ["/usr", "/bin", "/lib", "/lib64", "/usr/local",
                str(Path(sys.prefix)), str(real_python.parent)]
    if len(real_python.parents) > 2:
        prefixes.append(str(real_python.parents[2]))
    if len(real_python.parents) > 4:
        install_root = real_python.parents[4]
        if install_root != Path("/") and len(install_root.parts) >= 3:
            prefixes.append(str(install_root))

    seen = set()
    for location in prefixes:
        if location in seen or location == "/" or not Path(location).exists():
            continue
        seen.add(location)
        command += ["--ro-bind", location, location]

    rust_bins = []
    for toolchains in (Path.home() / ".rustup" / "toolchains",
                       Path("/opt/rust/toolchains")):
        if toolchains.is_dir():
            command += ["--ro-bind", str(toolchains), str(toolchains)]
            rust_bins += [str(path / "bin") for path in sorted(toolchains.iterdir())
                          if path.is_dir() and (path / "bin" / "cargo").is_file()]

    for location in ("/etc/ssl/certs", "/etc/resolv.conf", "/etc/hosts",
                     "/etc/nsswitch.conf"):
        if Path(location).exists():
            command += ["--ro-bind", location, location]

    command += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
                "--dir", "/tmp/home", "--bind", str(root), str(root)]
    command += _git_mounts(root, repo_root)
    path = ":".join(dict.fromkeys(
        rust_bins + [str(real_python.parent), str(Path(sys.prefix) / "bin"),
                     "/usr/local/bin", "/usr/bin", "/bin"]))
    command += ["--chdir", str(root), "--clearenv",
                "--setenv", "PATH", path,
                "--setenv", "HOME", "/tmp/home",
                "--setenv", "CI", "1",
                "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
                "--setenv", "PYTHONUNBUFFERED", "1",
                "--setenv", "GIT_CONFIG_NOSYSTEM", "1",
                "--setenv", "GIT_CONFIG_GLOBAL", "/dev/null",
                "--setenv", "GIT_TERMINAL_PROMPT", "0",
                "--", *argv]
    return command
