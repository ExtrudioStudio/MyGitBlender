import os
import subprocess
from pathlib import Path

_CREATION_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run(args, cwd, timeout=None):
    # GIT_TERMINAL_PROMPT=0 / GCM_INTERACTIVE=never: a credential prompt from
    # inside Blender has no terminal to show on - fail fast instead of
    # hanging Blender's UI forever.
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        creationflags=_CREATION_FLAGS,
        env=env,
        timeout=timeout,
    )


_ERROR_PATTERNS = (
    (("authentication failed", "could not read username", "could not read password",
      "terminal prompts disabled", "logon failed", "permission denied (publickey"),
     "GitHub sign-in problem - run Setup Health Check for help"),
    (("could not resolve host", "unable to access", "connection timed out",
      "connection refused", "network is unreachable"),
     "No internet connection, or the git host is unreachable"),
    (("repository not found", "does not appear to be a git repository"),
     "Repo not found - check the URL and that your account has access"),
    (("non-fast-forward", "fetch first", "not possible to fast-forward"),
     "The repo has newer changes from another machine - Pull first"),
    (("author identity unknown", "unable to auto-detect email address", "empty ident name"),
     "Git needs your name/email - run Setup Health Check to set it"),
)


def humanize_git_error(raw: str) -> str:
    lowered = (raw or "").lower()
    for needles, message in _ERROR_PATTERNS:
        if any(n in lowered for n in needles):
            return message
    first_line = next((ln for ln in (raw or "").splitlines() if ln.strip()), "unknown error")
    return f"Git error: {first_line.strip()}"


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


def get_identity(mirror_path: Path | None) -> tuple[str, str]:
    """Effective git user.name/user.email (mirror-local config included when
    the mirror exists). Empty strings when unset."""
    cwd = mirror_path if mirror_path and (mirror_path / ".git").exists() else Path.home()
    name = _run(["config", "user.name"], cwd).stdout.strip()
    email = _run(["config", "user.email"], cwd).stdout.strip()
    return name, email


def set_local_identity(mirror_path: Path, name: str, email: str) -> bool:
    """Set user.name/user.email only inside the mirror repo - never touch the
    customer's global git config."""
    if not (mirror_path / ".git").exists():
        return False
    ok_name = _run(["config", "user.name", name], mirror_path).returncode == 0
    ok_email = _run(["config", "user.email", email], mirror_path).returncode == 0
    return ok_name and ok_email


def check_remote(remote_url: str, timeout: float = 15.0) -> tuple[bool, str]:
    """Can we reach and read the remote right now? Runs from home dir - no
    mirror needed, so it works before first setup."""
    try:
        result = _run(["ls-remote", remote_url, "HEAD"], Path.home(), timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "Timed out - the git host didn't answer"
    if result.returncode == 0:
        return True, ""
    return False, humanize_git_error(result.stderr)


def git_available() -> bool:
    import shutil
    return shutil.which("git") is not None


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
