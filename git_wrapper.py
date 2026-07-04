import subprocess
from pathlib import Path

_CREATION_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run(args, cwd):
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        creationflags=_CREATION_FLAGS,
    )


def ensure_repo(mirror_path: Path, remote_url: str) -> tuple[bool, str]:
    git_dir = mirror_path / ".git"
    if git_dir.exists():
        result = _run(["remote", "set-url", "origin", remote_url], mirror_path)
        return result.returncode == 0, result.stderr

    mirror_path.mkdir(parents=True, exist_ok=True)
    result = _run(["clone", remote_url, "."], mirror_path)
    if result.returncode == 0:
        return True, result.stdout

    # Fall back to a fresh local repo if the remote couldn't be cloned
    # (e.g. it genuinely has no commits yet for some git hosts).
    result = _run(["init"], mirror_path)
    if result.returncode != 0:
        return False, result.stderr
    result = _run(["remote", "add", "origin", remote_url], mirror_path)
    return result.returncode == 0, result.stderr


def commit_all(mirror_path: Path, message: str) -> tuple[bool, str]:
    _run(["add", "-A"], mirror_path)
    result = _run(["commit", "-m", message], mirror_path)
    if result.returncode != 0:
        if "nothing to commit" in result.stdout.lower():
            return False, "nothing to commit"
        return False, result.stderr
    return True, result.stdout


def push(mirror_path: Path) -> tuple[bool, str]:
    result = _run(["push", "-u", "origin", "HEAD"], mirror_path)
    return result.returncode == 0, (result.stdout + result.stderr)


def merge_ff(mirror_path: Path) -> tuple[bool, str]:
    """Fast-forward to the already-fetched upstream. Local-only, no network."""
    result = _run(["merge", "--ff-only", "@{u}"], mirror_path)
    return result.returncode == 0, (result.stdout + result.stderr)


def fetch(mirror_path: Path) -> tuple[bool, str]:
    result = _run(["fetch", "origin"], mirror_path)
    return result.returncode == 0, (result.stdout + result.stderr)


def remote_ahead_count(mirror_path: Path) -> int:
    """How many commits the upstream has that HEAD doesn't (after a fetch)."""
    result = _run(["rev-list", "HEAD..@{u}", "--count"], mirror_path)
    if result.returncode != 0:
        return 0
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


def show_file_at_ref(mirror_path: Path, ref: str, filename: str) -> str | None:
    """Read a file's content at a given ref without touching the working tree."""
    result = _run(["show", f"{ref}:{filename}"], mirror_path)
    if result.returncode != 0:
        return None
    return result.stdout


def log(mirror_path: Path, count: int = 30) -> tuple[bool, str]:
    result = _run(["log", f"-n{count}", "--format=%H|%ci|%s"], mirror_path)
    return result.returncode == 0, result.stdout


def checkout_worktree_at(mirror_path: Path, commit_sha: str, dest_dir: Path) -> tuple[bool, str]:
    if dest_dir.exists():
        _run(["worktree", "remove", "--force", str(dest_dir)], mirror_path)
    result = _run(["worktree", "add", "--detach", str(dest_dir), commit_sha], mirror_path)
    return result.returncode == 0, (result.stdout + result.stderr)


def remove_worktree(mirror_path: Path, dest_dir: Path) -> None:
    _run(["worktree", "remove", "--force", str(dest_dir)], mirror_path)
