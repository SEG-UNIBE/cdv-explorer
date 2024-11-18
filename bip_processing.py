import os
import json
import re
from datetime import datetime
from collections import Counter
from typing import Dict, List, Tuple
import requests

# --- Constants ---
VALID_STATUSES = ['Draft', 'Active', 'Proposed', 'Deferred', 'Rejected', 'Withdrawn', 'Final', 'Replaced', 'Obsolete']
VALID_LICENSES = ['BSD-2-Clause', 'BSD-3-Clause', 'CC0-1.0', 'GNU-All-Permissive', 'Apache-2.0', 'BSL-1.0', 'CC-BY-4.0', 'CC-BY-SA-4.0', 'MIT', 'AGPL-3.0+', 'FDL-1.3', 'GPL-2.0+', 'LGPL-2.1+', 'PD', 'OPL']
VALID_LAYERS = ['Consensus (soft fork)', 'Consensus (hard fork)', 'Peer Services', 'API/RPC', 'Applications']
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "he", "in", "is", "it", "its", "of", "on", "that", "the",
    "to", "was", "were", "will", "with", "you", "your", "this", "or"
}

# --- Utility Functions ---
def load_github_token(token_file='github_token.txt') -> str:
    try:
        with open(token_file, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"GitHub token file '{token_file}' not found.")

def load_bip_content(file_path: str) -> str:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: File {file_path} not found.")
        return ""

def find_bip_file(bip_number: str, bip_dir: str) -> str:
    bip_file_md = f"bip-{bip_number}.md"
    bip_file_mediawiki = f"bip-{bip_number}.mediawiki"

    if os.path.exists(os.path.join(bip_dir, bip_file_md)):
        return os.path.join(bip_dir, bip_file_md)
    elif os.path.exists(os.path.join(bip_dir, bip_file_mediawiki)):
        return os.path.join(bip_dir, bip_file_mediawiki)
    else:
        return None

# --- Metadata Section ---
def get_git_history(bip_file: str, github_token: str) -> List[Tuple[str, str, str]]:
    headers = {"Authorization": f"token {github_token}"}
    url = f"https://api.github.com/repos/bitcoin/bips/commits?path={bip_file}"

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Error fetching commit data for {bip_file}: {response.status_code}")
        return []

    commits = response.json()
    history = [(commit.get("sha", ""),
                commit.get("commit", {}).get("committer", {}).get("date", ""),
                commit.get("commit", {}).get("committer", {}).get("name", "")) for commit in commits]

    return history

def get_unique_authors(history: List[Tuple[str, str, str]]) -> int:
    authors = {commit[2] for commit in history}
    return len(authors)

def update_metadata(json_data: Dict[str, any], bip_file_name: str, github_token: str):
    if "metadata" not in json_data:
        json_data["metadata"] = {
            "last_commit": None,
            "total_commits": None,
            "metadata_last_updated": None,
            "git_history": [],
            "contributors": None,
            "google_trend_index": None
        }

    commit_info = get_git_history(bip_file_name, github_token)
    if commit_info:
        last_commit_date = commit_info[0][1]
        contributors = get_unique_authors(commit_info)
    else:
        last_commit_date = None
        contributors = 0

    json_data["metadata"].update({
        "last_commit": last_commit_date,
        "total_commits": len(commit_info),
        "metadata_last_updated": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S'),
        "git_history": commit_info,
        "contributors": contributors
    })

    return json_data

# --- Compliance Checks ---
def check_title_length(preamble: Dict[str, any]) -> Dict[str, any]:
    title = preamble.get("title", "")
    return {"title_length_respected": len(title) <= 44, "title_length": len(title)}

def check_abstract_length_from_file(file_path: str) -> Dict[str, any]:
    raw_content = load_bip_content(file_path)
    abstract_pattern = re.compile(r"==\s*Abstract\s*==", re.IGNORECASE)
    match = abstract_pattern.search(raw_content)

    if not match:
        return {"abstract_length_respected": False, "abstract_word_count": 0, "error": "Abstract section not found"}

    abstract_start = match.end()
    next_headline = re.search(r"==\s*[^\n]+\s*==", raw_content[abstract_start:], re.IGNORECASE)
    abstract_end = next_headline.start() + abstract_start if next_headline else len(raw_content)
    abstract_text = raw_content[abstract_start:abstract_end].strip()
    word_count = len(abstract_text.split())

    return {"abstract_length_respected": word_count <= 200, "abstract_word_count": word_count}

def run_compliance_checks(file_path: str, preamble: Dict[str, any]) -> Dict[str, any]:
    required_fields = ["bip", "title", "author", "comments_uri", "status", "type", "created", "license"]
    missing_fields = [field for field in required_fields if not preamble.get(field)]

    return {
        "compliance": {
            "title_length_respected": check_title_length(preamble)["title_length_respected"],
            **check_abstract_length_from_file(file_path),
            "required_fields_present": len(missing_fields) == 0,
            "missing_fields": missing_fields
        }
    }

# --- Insights Section ---
def create_word_list(raw_content: str) -> Dict[str, int]:
    words = re.findall(r'\b\w+\b', raw_content.lower())
    filtered_words = [word for word in words if word not in STOP_WORDS]
    return dict(Counter(filtered_words).most_common())

def update_insights(json_data: Dict[str, any], bip_file_path: str):
    if "insights" not in json_data:
        json_data["insights"] = {}

    raw_section = json_data.get("raw", {})
    preamble = raw_section.get("preamble", {})
    raw_content = load_bip_content(bip_file_path)

    json_data["insights"].update(run_compliance_checks(bip_file_path, preamble))
    json_data["insights"]["word_list"] = create_word_list(raw_content)

# --- Main Processing Function ---
def process_bip_files(input_dir: str, output_dir: str, github_token: str):
    json_files = [f for f in os.listdir(input_dir) if f.endswith('.json')]
    for json_file in json_files:
        file_path = os.path.join(input_dir, json_file)
        with open(file_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)

        preamble = json_data.get("raw", {}).get("preamble", {})
        if not preamble:
            print(f"No preamble found in {json_file}")
            continue

        bip_number = preamble.get("bip", "").zfill(4)
        bip_file_path = find_bip_file(bip_number, 'bips_downloaded')
        if not bip_file_path:
            print(f"No file found for BIP-{bip_number}")
            continue

        relative_bip_path = os.path.relpath(bip_file_path, start='bips_downloaded')
        json_data = update_metadata(json_data, relative_bip_path, github_token)
        update_insights(json_data, bip_file_path)

        output_path = os.path.join(output_dir, json_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        print(f"Processed {json_file}")
