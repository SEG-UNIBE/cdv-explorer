import os
import subprocess
import threading
import queue
import re
from pathlib import Path

# GitHub repository details
OWNER = 'bitcoin'
REPO = 'bips'
REPO_URL = f'https://github.com/{OWNER}/{REPO}.git'

# Local directory to save the repository
LOCAL_DIR = Path(f"{REPO}_cloned")

# Queue for multithreading
file_queue = queue.Queue()

# Regular expressions for BIP files and directories
BIP_FILE_PATTERN = re.compile(r'^bip-\d{4}\.(mediawiki|md|rst)$', re.IGNORECASE)
BIP_DIR_PATTERN = re.compile(r'^bip-\d{4}$', re.IGNORECASE)


def clone_or_update_repo():
    """Clone the repository if not already cloned, otherwise update it."""
    if LOCAL_DIR.exists():
        print("Repository already exists. Pulling latest changes...")
        subprocess.run(['git', '-C', str(LOCAL_DIR), 'pull'], check=True)
    else:
        print("Cloning repository...")
        subprocess.run(['git', 'clone', REPO_URL, str(LOCAL_DIR)], check=True)


def process_directory(directory: Path):
    """Process the root directory and BIP directories."""
    for item in directory.iterdir():
        if item.is_file() and BIP_FILE_PATTERN.match(item.name):
            file_queue.put(item)
        elif item.is_dir() and BIP_DIR_PATTERN.match(item.name):
            process_bip_directory(item)


def process_bip_directory(directory: Path):
    """Recursively process BIP directories and queue files for processing."""
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


def process_bips(num_threads=5):
    """Main function to process all BIPs and associated directories."""
    threads = [threading.Thread(target=worker) for _ in range(num_threads)]
    for t in threads:
        t.start()

    process_directory(LOCAL_DIR)

    file_queue.join()

    for _ in threads:
        file_queue.put(None)
    for t in threads:
        t.join()


def download_bips():
    clone_or_update_repo()
    process_bips()
