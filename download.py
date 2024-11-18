import requests
import os
import threading
import queue
import re

# GitHub repository details
OWNER = 'bitcoin'
REPO = 'bips'

# Optional: Your GitHub personal access token
TOKEN = ''  # Replace with your token or leave empty for unauthenticated requests

# Headers for API requests
HEADERS = {'Authorization': f'token {TOKEN}'} if TOKEN else {}

# Base API URL
API_URL = f'https://api.github.com/repos/{OWNER}/{REPO}/contents'

# Local directory to save the repository
LOCAL_DIR = f'{REPO}_downloaded'

# Queue for multithreading
file_queue = queue.Queue()

# Regular expressions for BIP files and directories
BIP_FILE_PATTERN = re.compile(r'^bip-\d{4}\.(mediawiki|md|rst)$', re.IGNORECASE)
BIP_DIR_PATTERN = re.compile(r'^bip-\d{4}$', re.IGNORECASE)


def download_file(file_info):
    """Download a file from GitHub and save it locally."""
    path = file_info['path']
    download_url = file_info['download_url']
    local_path = os.path.join(LOCAL_DIR, path)

    # Create local directory if it doesn't exist
    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    # Download the file
    try:
        response = requests.get(download_url, headers=HEADERS)
        response.raise_for_status()

        # Write the file content
        with open(local_path, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded: {path}")
    except Exception as e:
        print(f"Failed to download {path}: {e}")


def process_directory(dir_url, current_path=''):
    """Process the root directory and BIP directories."""
    try:
        response = requests.get(dir_url, headers=HEADERS)
        response.raise_for_status()
        items = response.json()

        for item in items:
            item_name = item['name']
            item_path = os.path.join(current_path, item_name)
            if item['type'] == 'file' and BIP_FILE_PATTERN.match(item_name):
                # Add BIP file in root directory to the queue
                file_queue.put(item)
            elif item['type'] == 'dir' and BIP_DIR_PATTERN.match(item_name):
                # Process BIP directories and download all files inside
                process_bip_directory(item['url'], item_path)
    except Exception as e:
        print(f"Failed to process directory {dir_url}: {e}")


def process_bip_directory(dir_url, current_path):
    """Recursively process BIP directories and download all files."""
    try:
        response = requests.get(dir_url, headers=HEADERS)
        response.raise_for_status()
        items = response.json()

        for item in items:
            item_name = item['name']
            item_path = os.path.join(current_path, item_name)
            if item['type'] == 'file':
                # Add file to the queue for downloading
                file_info = item.copy()
                file_info['path'] = item_path  # Update the path to include subdirectories
                file_queue.put(file_info)
            elif item['type'] == 'dir':
                # Recursively process subdirectories
                process_bip_directory(item['url'], item_path)
            else:
                print(f"Unknown item type: {item['type']} at {item_path}")
    except Exception as e:
        print(f"Failed to process BIP directory {dir_url}: {e}")


def worker():
    """Worker thread function for downloading files."""
    while True:
        file_info = file_queue.get()
        if file_info is None:
            break
        download_file(file_info)
        file_queue.task_done()


def download_bips(num_threads=5):
    """Main function to download all BIPs and associated directories."""
    threads = [threading.Thread(target=worker) for _ in range(num_threads)]
    for t in threads:
        t.start()

    process_directory(API_URL)

    file_queue.join()

    for _ in threads:
        file_queue.put(None)
    for t in threads:
        t.join()
