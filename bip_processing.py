import json
import os
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from openai import OpenAI

# --- Constants ---
LOCAL_REPO_DIR = Path("bips_cloned")  # Path to the cloned repository
STOP_WORDS = {"a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
              "has", "he", "in", "is", "it", "its", "of", "on", "that", "the",
              "to", "was", "were", "will", "with", "you", "your", "this", "or"}

# --- Utility Functions ---
def load_bip_content(file_path: Path) -> str:
    try:
        with file_path.open('r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: File {file_path} not found.")
        return ""

def find_bip_file(bip_number: str) -> Path:
    bip_file_md = LOCAL_REPO_DIR / f"bip-{bip_number}.md"
    bip_file_mediawiki = LOCAL_REPO_DIR / f"bip-{bip_number}.mediawiki"
    
    if bip_file_md.exists():
        return bip_file_md
    elif bip_file_mediawiki.exists():
        return bip_file_mediawiki
    return None

def get_git_history(file_path: Path) -> List[Tuple[str, str, str]]:
    """Retrieve commit history for a file using local Git."""
    try:
        result = subprocess.run(
            ["git", "-C", str(LOCAL_REPO_DIR), "log", "--pretty=format:%H|%ad|%an", "--", str(file_path)],
            capture_output=True, text=True, check=True
        )
        commits = [line.split('|') for line in result.stdout.strip().split('\n') if line]
        return [(commit[0], commit[1], commit[2]) for commit in commits]
    except subprocess.CalledProcessError:
        print(f"Error retrieving commit history for {file_path}")
        return []

def get_unique_authors(history: List[Tuple[str, str, str]]) -> int:
    return len(set(commit[2] for commit in history))

def update_metadata(json_data: Dict[str, any], bip_file_path: Path):
    """Update metadata section with Git commit history."""
    if "metadata" not in json_data:
        json_data["metadata"] = {
            "last_commit": None,
            "total_commits": None,
            "metadata_last_updated": None,
            "git_history": [],
            "contributors": None,
        }
    
    commit_info = get_git_history(bip_file_path)
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

def create_word_list(raw_content: str) -> Dict[str, int]:
    words = re.findall(r'\b\w+\b', raw_content.lower())
    filtered_words = [word for word in words if word not in STOP_WORDS]
    return dict(Counter(filtered_words).most_common())


def create_bip_list(raw_content: str) -> List[str]:
    # Extract BIP references (e.g., BIP-0032, BIP 39, BIP#042)
    bip_pattern = r"\bBIP[-#\s]?(\d+)\b"
    bip_references = re.findall(bip_pattern, raw_content)

    # Normalize BIP references, removing leading zeros
    return sorted(set(f"BIP {int(num)}" for num in bip_references))

def llm_bip_dependencies(text, current_bip_number=None):

    prompt = f"""
You are analyzing the text of Bitcoin Improvement Proposal (BIP){f" {current_bip_number}" if current_bip_number else ""}.

The goal is to identify any dependencies to other BIPs

Example 1:
Text: This BIP proposes a change to the key format. It depends on BIP 32 and BIP 39.
Dependencies: ["BIP 32", "BIP 39"]

Example 2:
Text: This proposal builds upon BIP-0016 for partially signed transactions.
Dependencies: ["BIP 16"]

Example 3:
Text: This BIP does not depend on any other BIPs.
Dependencies: []

Respond with a plain JSON array of BIP numbers that this BIP depends on. For example:
["BIP 32","BIP 327","BIP 328","BIP 380"]

If there are no dependencies, return an empty list.

No text, no explanation, no formatting. Only the JSON list.

Here is the BIP text:

\"\"\"{text}\"\"\"
"""
    
    model="gpt-3.5-turbo"
    api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        print(response.choices[0].message.content.strip())
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        print(f"[!] Error: {e}")
        return ["error"]

    

def update_insights(json_data: Dict[str, any], bip_file_path: Path):
    """Generate insights for a BIP file."""
    raw_content = load_bip_content(bip_file_path)
    json_data.setdefault("insights", {})
    # Generate insights
    json_data["insights"]["word_list"] = create_word_list(raw_content)
    json_data["insights"]["bip_references"] = create_bip_list(raw_content)
    json_data["insights"]["dependencies"] = llm_bip_dependencies(raw_content,str(int(json_data["raw"]["preamble"]["bip"])))

    # Remove reference to the BIP itself
    bip_number = str(int(json_data["raw"]["preamble"]["bip"]))  # Remove leading zeros
    json_data["insights"]["bip_references"] = [
        bip for bip in json_data["insights"]["bip_references"] if bip != f"BIP {bip_number}"
    ]

def process_bip_files(input_dir: Path, output_dir: Path):
    """Process all BIP JSON files and update metadata & insights."""
    json_files = [f for f in input_dir.iterdir() if f.suffix == '.json']
    for json_file in json_files:
        with json_file.open('r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        preamble = json_data.get("raw", {}).get("preamble", {})
        bip_number = str(preamble.get("bip", "")).zfill(4)
        bip_file_path = find_bip_file(bip_number)
        
        if not bip_file_path:
            print(f"No file found for BIP-{bip_number}")
            continue
        
        json_data = update_metadata(json_data, bip_file_path)
        update_insights(json_data, bip_file_path)
        
        output_path = output_dir / json_file.name
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        print(f"Processed {json_file.name}")
