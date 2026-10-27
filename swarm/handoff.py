"""Hand the delivered artifact to version control.

RATBAG does not review its own work and does not merge. It commits what the
factory produced and pushes one branch — `preview` by default — so a reviewer
(FatChin) can pick it up. Never force, never rewrite, never touch the default
branch.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


IDENTITY = ("-c", "user.name=RATBAG", "-c", "user.email=ratbag@localhost")


class HandoffError(RuntimeError):
    """Git refused, or the remote could not be reached."""


@dataclass
class Handoff:
    repo: str
    branch: str
    commit: str
    remote: str
    pushed: bool

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "branch": self.branch,
            "commit": self.commit,
            "remote": self.remote,
            "pushed": self.pushed,
        }


def _git(workspace: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(workspace), *args],
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()[-400:]
        raise HandoffError(detail or f"git {args[0]} failed")
    return result


def _has_head(workspace: Path) -> bool:
    return _git(workspace, "rev-parse", "--verify", "HEAD", check=False).returncode == 0


def publish(workspace: str | Path, remote: str = "", branch: str = "preview", message: str = "") -> Handoff:
    """Commit the workspace and push one branch. Safe to call twice."""
    root = Path(workspace).expanduser().resolve()
    if not root.is_dir():
        raise HandoffError(f"The workspace does not exist: {root}")

    gitignore = root / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(".sdlc_factory/\n.venv/\n__pycache__/\n*.pyc\n", encoding="utf-8")

    if not (root / ".git").exists():
        _git(root, "init", "-b", "main")

    status = _git(root, "status", "--porcelain").stdout.strip()
    if status:
        _git(root, "add", "-A")
        _git(root, *IDENTITY, "commit", "-m", message or "feat: delivered artifact and its evidence")
    elif not _has_head(root):
        _git(root, *IDENTITY, "commit", "--allow-empty", "-m", message or "chore: delivered artifact")

    commit = _git(root, "rev-parse", "HEAD").stdout.strip()

    resolved_remote = remote.strip()
    if resolved_remote:
        existing = _git(root, "remote", "get-url", "origin", check=False)
        if existing.returncode == 0:
            _git(root, "remote", "set-url", "origin", resolved_remote)
        else:
            _git(root, "remote", "add", "origin", resolved_remote)

    has_origin = _git(root, "remote", "get-url", "origin", check=False).returncode == 0
    if not has_origin:
        return Handoff(repo=str(root), branch=branch, commit=commit, remote="", pushed=False)

    origin = _git(root, "remote", "get-url", "origin").stdout.strip()
    pushed = _git(root, "push", "--set-upstream", "origin", f"HEAD:refs/heads/{branch}", check=False)
    if pushed.returncode != 0:
        detail = (pushed.stderr or pushed.stdout or "").strip()[-500:]
        raise HandoffError(
            detail or f"The commit was made locally, but pushing {branch} to {origin} failed."
        )
    return Handoff(repo=str(root), branch=branch, commit=commit, remote=origin, pushed=True)
