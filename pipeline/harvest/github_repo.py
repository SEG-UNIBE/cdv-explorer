import re
import subprocess
import threading
import queue
from pathlib import Path


def _clone_or_update(repo_url: str, local_dir: Path) -> None:
    if local_dir.exists():
        if not any(local_dir.iterdir()):
            subprocess.run(["git", "clone", repo_url, str(local_dir)], check=True)
            return
        if not (local_dir / ".git").exists():
            raise ValueError(f"{local_dir} exists but is not a git repository.")
        subprocess.run(["git", "-C", str(local_dir), "fetch", "--all", "--prune"], check=True)
        return
    local_dir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", repo_url, str(local_dir)], check=True)


def _default_branch_ref(local_dir: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(local_dir), "symbolic-ref", "refs/remotes/origin/HEAD"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        pass

    for candidate in ("origin/master", "origin/main"):
        try:
            subprocess.run(
                ["git", "-C", str(local_dir), "rev-parse", "--verify", candidate],
                capture_output=True, text=True, check=True,
            )
            return candidate
        except subprocess.CalledProcessError:
            continue

    raise RuntimeError("Could not determine the repository default branch.")


def _checkout_snapshot(local_dir: Path, snapshot: str) -> None:
    branch_ref = _default_branch_ref(local_dir)
    result = subprocess.run(
        ["git", "-C", str(local_dir), "rev-list", "-1", f"--before={snapshot} 23:59:59", branch_ref],
        capture_output=True, text=True, check=True,
    )
    commit_hash = result.stdout.strip()
    if not commit_hash:
        raise ValueError(f"No commit found on or before {snapshot}.")
    subprocess.run(["git", "-C", str(local_dir), "checkout", "--detach", commit_hash], check=True)


def _scan_files(local_dir: Path, file_pattern: re.Pattern, dir_pattern: re.Pattern) -> None:
    file_q: queue.Queue = queue.Queue()

    def _enqueue_dir(directory: Path) -> None:
        for item in directory.iterdir():
            if item.is_file() and file_pattern.match(item.name):
                file_q.put(item)
            elif item.is_dir() and dir_pattern.match(item.name):
                for sub in item.rglob("*"):
                    if sub.is_file():
                        file_q.put(sub)

    threads = [threading.Thread(target=lambda: None) for _ in range(5)]
    _enqueue_dir(local_dir)

    for _ in threads:
        file_q.put(None)


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

    repo_state = "Fetching repository updates" if local_dir.exists() else "Cloning repository"
    _emit(progress_callback, repo_state)
    _clone_or_update(repo_url, local_dir)

    _emit(progress_callback, f"Checking out snapshot for {snapshot}", advance=1)
    _checkout_snapshot(local_dir, snapshot)

    _emit(progress_callback, "Scanning proposal files", advance=1)
    file_pattern = re.compile(src_config["document_file_pattern"], re.IGNORECASE)
    dir_pattern_str = src_config.get("document_dir_pattern", "^$")
    dir_pattern = re.compile(dir_pattern_str, re.IGNORECASE)
    _scan_files(local_dir, file_pattern, dir_pattern)

    _emit(progress_callback, "Completed", advance=1)
    return local_dir
