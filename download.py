import subprocess
import threading
import queue
import re
from pathlib import Path
from ecosystem_config import ACTIVE_ECOSYSTEM

# GitHub repository details
OWNER = ACTIVE_ECOSYSTEM["repository_owner"]
REPO = ACTIVE_ECOSYSTEM["repository_name"]
REPO_URL = f'https://github.com/{OWNER}/{REPO}.git'

# Local directory to save the repository
CLONE_ROOT = Path(ACTIVE_ECOSYSTEM["clone_directory"])

# Queue for multithreading
file_queue = queue.Queue()

# Regular expressions for proposal files and directories
PROPOSAL_FILE_PATTERN = re.compile(ACTIVE_ECOSYSTEM["document_file_pattern"], re.IGNORECASE)
PROPOSAL_DIR_PATTERN = re.compile(ACTIVE_ECOSYSTEM["document_dir_pattern"], re.IGNORECASE)


def clone_or_update_repo(local_dir: Path):
    """Clone the repository if not already cloned, otherwise fetch updates."""
    if local_dir.exists():
        if not (local_dir / ".git").exists():
            raise ValueError(f"{local_dir} exists but is not a git repository.")

        print(f"Repository already exists in {local_dir}. Fetching latest changes...")
        subprocess.run(['git', '-C', str(local_dir), 'fetch', '--all', '--prune'], check=True)
        return

    local_dir.parent.mkdir(parents=True, exist_ok=True)
    print(f"Cloning repository into {local_dir}...")
    subprocess.run(['git', 'clone', REPO_URL, str(local_dir)], check=True)


def get_default_branch_ref(local_dir: Path) -> str:
    """Return the remote default branch ref for the repository."""
    try:
        result = subprocess.run(
            ['git', '-C', str(local_dir), 'symbolic-ref', 'refs/remotes/origin/HEAD'],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        for candidate in ('origin/master', 'origin/main'):
            try:
                subprocess.run(
                    ['git', '-C', str(local_dir), 'rev-parse', '--verify', candidate],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return candidate
            except subprocess.CalledProcessError:
                continue

    raise RuntimeError("Could not determine the repository default branch.")


def checkout_stichtag(local_dir: Path, stichtag: str):
    """Check out the latest commit on or before the given STICHTAG date."""
    branch_ref = get_default_branch_ref(local_dir)
    result = subprocess.run(
        ['git', '-C', str(local_dir), 'rev-list', '-1', f'--before={stichtag} 23:59:59', branch_ref],
        capture_output=True,
        text=True,
        check=True,
    )
    commit_hash = result.stdout.strip()
    if not commit_hash:
        raise ValueError(f"No commit found on or before {stichtag}.")

    print(f"Checking out commit {commit_hash} for STICHTAG {stichtag}...")
    subprocess.run(['git', '-C', str(local_dir), 'checkout', '--detach', commit_hash], check=True)


def process_directory(directory: Path):
    """Process the root directory and proposal directories."""
    for item in directory.iterdir():
        if item.is_file() and PROPOSAL_FILE_PATTERN.match(item.name):
            file_queue.put(item)
        elif item.is_dir() and PROPOSAL_DIR_PATTERN.match(item.name):
            process_bip_directory(item)


def process_bip_directory(directory: Path):
    """Recursively process proposal directories and queue files for processing."""
    for item in directory.rglob("*"):
        if item.is_file():
            file_queue.put(item)


def worker():
    """Worker thread function for processing files."""
    while True:
        file = file_queue.get()
        if file is None:
            break
        print(f"Processing: {file}")
        file_queue.task_done()


def process_bips(local_dir: Path, num_threads=5):
    """Main function to process all proposal files and associated directories."""
    threads = [threading.Thread(target=worker) for _ in range(num_threads)]
    for t in threads:
        t.start()

    process_directory(local_dir)

    file_queue.join()

    for _ in threads:
        file_queue.put(None)
    for t in threads:
        t.join()


def download_bips(stichtag: str, local_dir: Path | None = None):
    local_dir = local_dir or CLONE_ROOT
    clone_or_update_repo(local_dir)
    checkout_stichtag(local_dir, stichtag)
    process_bips(local_dir)
    return local_dir
