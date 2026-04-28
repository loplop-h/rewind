"""Safety pre-flight checks for rollbacks.

We enforce two invariants before mutating the file system:

1. **Cwd containment.** Every path we plan to write is inside the configured
   working directory. Otherwise rollback could clobber unrelated files on
   disk (e.g. dotfiles in ``$HOME``).
2. **Clean working tree.** If the cwd is a git repo and has uncommitted
   changes, refuse unless ``--force`` is set. The user has work-in-progress
   that the rollback would silently overwrite.

Both checks raise :class:`SafetyError` on failure. The caller decides how
to surface that to the user (CLI prints, TUI dialog, etc.).
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterable
from pathlib import Path


class SafetyError(RuntimeError):
    """Raised when a rollback would violate a safety invariant."""


def check_paths_within_cwd(paths: Iterable[Path], cwd: Path) -> None:
    """Raise if any path is outside ``cwd`` (after resolving symlinks)."""

    cwd_resolved = cwd.resolve()
    bad: list[str] = []
    for raw in paths:
        target = Path(raw).resolve()
        try:
            target.relative_to(cwd_resolved)
        except ValueError:
            bad.append(str(target))
    if bad:
        joined = ", ".join(bad)
        raise SafetyError(f"refusing to rollback paths outside cwd ({cwd_resolved}): {joined}")


def check_uncommitted_changes(cwd: Path) -> None:
    """Raise if ``cwd`` is a git repo and has uncommitted changes.

    Treats non-git or git-not-installed as a no-op: the safety net only
    applies when we can actually verify the working tree.
    """

    if not _is_git_repo(cwd):
        return
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "status", "--porcelain"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return
    if result.returncode != 0:
        return
    output = result.stdout.strip()
    if output:
        raise SafetyError(
            "refusing to rollback: working tree has uncommitted changes "
            "(commit, stash, or pass --force)"
        )


def _is_git_repo(cwd: Path) -> bool:
    git_dir = cwd / ".git"
    if git_dir.exists():
        return True
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--is-inside-work-tree"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"
