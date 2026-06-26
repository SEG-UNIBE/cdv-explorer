import subprocess
from pathlib import Path


def _clone_or_update(repo_url: str, local_dir: Path, progress_callback=None) -> None:
    if local_dir.exists():
        if not any(local_dir.iterdir()):
            subprocess.run(["git", "clone", repo_url, str(local_dir)], check=True)
            return
        if not (local_dir / ".git").exists():
            raise ValueError(f"{local_dir} exists but is not a git repository.")
        try:
            subprocess.run(
                ["git", "-C", str(local_dir), "fetch", "--all", "--prune"], check=True
            )
        except subprocess.CalledProcessError:
            _emit(progress_callback, "Fetch failed; using existing local repository")
        return
    local_dir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", repo_url, str(local_dir)], check=True)


def _default_branch_ref(local_dir: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(local_dir), "symbolic-ref", "refs/remotes/origin/HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        pass

    for candidate in ("origin/master", "origin/main"):
        try:
            subprocess.run(
                ["git", "-C", str(local_dir), "rev-parse", "--verify", candidate],
                capture_output=True,
                text=True,
                check=True,
            )
            return candidate
        except subprocess.CalledProcessError:
            continue

    raise RuntimeError("Could not determine the repository default branch.")


def _checkout_snapshot(local_dir: Path, snapshot: str) -> None:
    branch_ref = _default_branch_ref(local_dir)
    result = subprocess.run(
        [
            "git",
            "-C",
            str(local_dir),
            "rev-list",
            "-1",
            f"--before={snapshot} 23:59:59",
            branch_ref,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    commit_hash = result.stdout.strip()
    if not commit_hash:
        raise ValueError(f"No commit found on or before {snapshot}.")
    subprocess.run(
        ["git", "-C", str(local_dir), "checkout", "--force", "--detach", commit_hash],
        check=True,
    )


def _emit(progress_callback, message: str | None = None, advance: int = 0) -> None:
    if progress_callback is not None:
        progress_callback(message, advance)


def harvest(
    src_config: dict,
    snapshot: str,
    local_dir: Path,
    progress_callback=None,
) -> Path:
    """Clone/fetch the GitHub repo and check out the snapshot date."""
    owner = src_config["repository_owner"]
    repo = src_config["repository_name"]
    repo_url = f"https://github.com/{owner}/{repo}.git"

    repo_state = (
        "Fetching repository updates" if local_dir.exists() else "Cloning repository"
    )
    _emit(progress_callback, repo_state)
    _clone_or_update(repo_url, local_dir, progress_callback=progress_callback)

    _emit(progress_callback, f"Checking out snapshot for {snapshot}", advance=1)
    _checkout_snapshot(local_dir, snapshot)

    _emit(progress_callback, "Scanning proposal files", advance=1)
    _emit(progress_callback, "Completed", advance=1)
    return local_dir
