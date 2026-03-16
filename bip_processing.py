import json
import os
import re
import subprocess
from collections import Counter
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Dict, List, Tuple

from openai import OpenAI
from ecosystem_config import ACTIVE_ECOSYSTEM

PROPOSAL_LABEL = ACTIVE_ECOSYSTEM["proposal_acronym"]
PROPOSAL_SINGULAR = ACTIVE_ECOSYSTEM["proposal_term_singular"]
PRIMARY_ID_FIELD = ACTIVE_ECOSYSTEM["primary_id_field"]
DOCUMENT_PREFIX = ACTIVE_ECOSYSTEM["document_prefix"]
REFERENCE_PATTERN = ACTIVE_ECOSYSTEM["reference_pattern"]

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

def find_bip_file(repo_dir: Path, bip_number: str, file_prefix: str = DOCUMENT_PREFIX) -> Path:
    bip_file_md = repo_dir / f"{file_prefix}-{bip_number}.md"
    bip_file_mediawiki = repo_dir / f"{file_prefix}-{bip_number}.mediawiki"
    
    if bip_file_md.exists():
        return bip_file_md
    elif bip_file_mediawiki.exists():
        return bip_file_mediawiki
    return None

def get_git_history(repo_dir: Path, file_path: Path) -> List[Tuple[str, str, str]]:
    """Retrieve commit history for a file using local Git."""
    try:
        relative_file_path = file_path.relative_to(repo_dir)
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "log", "--pretty=format:%H|%ad|%an", "--", str(relative_file_path)],
            capture_output=True, text=True, check=True
        )
        commits = [line.split('|') for line in result.stdout.strip().split('\n') if line]
        return [(commit[0], commit[1], commit[2]) for commit in commits]
    except subprocess.CalledProcessError:
        print(f"Error retrieving commit history for {file_path}")
        return []

def get_unique_authors(history: List[Tuple[str, str, str]]) -> int:
    return len(set(commit[2] for commit in history))

def update_metadata(json_data: Dict[str, any], bip_file_path: Path, repo_dir: Path):
    """Update metadata section with Git commit history."""
    if "metadata" not in json_data:
        json_data["metadata"] = {
            "last_commit": None,
            "total_commits": None,
            "metadata_last_updated": None,
            "git_history": [],
            "contributors": None,
        }
    
    commit_info = get_git_history(repo_dir, bip_file_path)
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


def create_reference_list(raw_content: str, proposal_label: str = PROPOSAL_LABEL) -> List[str]:
    proposal_references = re.findall(REFERENCE_PATTERN, raw_content)

    return sorted(set(f"{proposal_label} {int(num)}" for num in proposal_references))

def llm_bip_dependencies(text, current_bip_number=None, proposal_label: str = PROPOSAL_LABEL):

    prompt = f"""
You are analyzing the text of {PROPOSAL_SINGULAR} ({proposal_label}){f" {current_bip_number}" if current_bip_number else ""}.

The goal is to identify any dependencies to other {proposal_label}s

Example 1:
Text: This proposal proposes a change to the key format. It depends on {proposal_label} 32 and {proposal_label} 39.
Dependencies: ["{proposal_label} 32", "{proposal_label} 39"]

Example 2:
Text: This proposal builds upon {proposal_label}-0016 for partially signed transactions.
Dependencies: ["{proposal_label} 16"]

Example 3:
Text: This proposal does not depend on any other {proposal_label}s.
Dependencies: []

Respond with a plain JSON array of proposal numbers that this proposal depends on. For example:
["{proposal_label} 32","{proposal_label} 327","{proposal_label} 328","{proposal_label} 380"]

If there are no dependencies, return an empty list.

No text, no explanation, no formatting. Only the JSON list.

Here is the proposal text:

\"\"\"{text}\"\"\"
"""
    
    model="gpt-5-mini"
    api_key = load_api_key()
    client = OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        print(response.choices[0].message.content.strip())
        return json.loads(response.choices[0].message.content.strip())
    except (JSONDecodeError, TypeError, ValueError, KeyError) as e:
        print(f"[!] Error: {e}")
        return ["error"]

def load_api_key():
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key
    with open("apikey.secret", encoding="utf-8") as f:
        return f.read().strip()

def update_insights(
    json_data: Dict[str, any],
    bip_file_path: Path,
    proposal_label: str = PROPOSAL_LABEL,
    id_field: str = PRIMARY_ID_FIELD,
):
    """Generate insights for a BIP file."""
    raw_content = load_bip_content(bip_file_path)
    json_data.setdefault("insights", {})
    # Generate insights
    json_data["insights"]["word_list"] = create_word_list(raw_content)
    references = create_reference_list(raw_content, proposal_label=proposal_label)
    json_data["insights"]["references"] = references
    json_data["insights"]["bip_references"] = references
    json_data["insights"]["dependencies"] = llm_bip_dependencies(
        raw_content,
        str(int(json_data["raw"]["preamble"][id_field])),
        proposal_label=proposal_label,
    )

    bip_number = str(int(json_data["raw"]["preamble"][id_field]))
    filtered_references = [
        bip for bip in references if bip != f"{proposal_label} {bip_number}"
    ]
    json_data["insights"]["references"] = filtered_references
    json_data["insights"]["bip_references"] = filtered_references

def process_bip_files(
    input_dir: Path,
    output_dir: Path,
    repo_dir: Path,
    file_prefix: str = DOCUMENT_PREFIX,
    proposal_label: str = PROPOSAL_LABEL,
    id_field: str = PRIMARY_ID_FIELD,
):
    """Process all BIP JSON files and update metadata & insights."""
    json_files = [f for f in input_dir.iterdir() if f.suffix == '.json']
    for json_file in json_files:
        with json_file.open('r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        preamble = json_data.get("raw", {}).get("preamble", {})
        bip_number = str(preamble.get(id_field, "")).zfill(4)
        bip_file_path = find_bip_file(repo_dir, bip_number, file_prefix=file_prefix)
        
        if not bip_file_path:
            print(f"No file found for {proposal_label}-{bip_number}")
            continue
        
        json_data = update_metadata(json_data, bip_file_path, repo_dir)
        update_insights(json_data, bip_file_path, proposal_label=proposal_label, id_field=id_field)
        
        output_path = output_dir / json_file.name
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        print(f"Processed {json_file.name}")
