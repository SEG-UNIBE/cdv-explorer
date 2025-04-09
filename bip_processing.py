import os
import json
import re
import subprocess
from datetime import datetime
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple
import spacy
import subprocess
import json



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

def normalize_bip(bip_string):
    num = re.search(r'\d+', bip_string)
    return f"BIP {int(num.group())}" if num else bip_string

def is_dependency_relation(doc, bip_string):
    DEPENDENCY_TRIGGERS = {"depend", "require", "rely", "use", "build", "extend", "supersede", "replace"}
    bip_tokens = [token for token in doc if bip_string in token.text]
    for token in doc:
        if token.lemma_ in DEPENDENCY_TRIGGERS and token.pos_ == "VERB":
            for child in token.subtree:
                if any(bip in child.text for bip in bip_tokens):
                    return True, token.lemma_, normalize_bip(bip_string)
    return False, None, None

def analyze_bip_dependencies(text):
    results = []
    all_bips = create_bip_list(text)
    nlp = spacy.load("en_core_web_sm")
    for sent in text.split('\n'):
        if not sent.strip():
            continue
        doc = nlp(sent)
        for bip in all_bips:
            if bip in sent:
                dep_found, verb, target_bip = is_dependency_relation(doc, bip)
                if dep_found:
                    results.append({
                        "sentence": sent.strip(),
                        "verb": verb,
                        "target_bip": target_bip
                    })
    return results

def run_ollama(prompt):
    OLLAMA_MODEL = "mistral:instruct"
    try:
        result = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL],
            input=prompt.encode('utf-8'),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        output = result.stdout.decode('utf-8').strip()

        try:
            json_output = json.loads(output.split('```json')[-1].split('```')[0] if '```json' in output else output)
            return json_output
        except Exception as e:
            print("[!] JSON parse error:", e)
            print("Raw output:", output)
            return None
    except Exception as e:
        print("[!] Ollama execution failed:", e)
        return None

def llm_bip_dependencies(text, current_bip_number=None):
    all_bips = create_bip_list(text)

    if current_bip_number:
        all_bips = [b for b in all_bips if b != current_bip_number]

    prompt = f"""
You are analyzing the text of Bitcoin Improvement Proposal (BIP){f" {current_bip_number}" if current_bip_number else ""}.

The goal is to identify any dependencies to other BIPs from this list:
{', '.join(all_bips)}

Respond with a plain JSON array of BIP numbers that this BIP depends on. For example:
["BIP 32","BIP 327","BIP 328","BIP 380"]

If there are no dependencies, return an empty list.

No text, no explanation, no formatting. Only the JSON list.

Here is the BIP text:

\"\"\"{text}\"\"\"
"""

    response = run_ollama(prompt)

    if isinstance(response, list):
        return response
    elif isinstance(response, dict) and "dependencies" in response:
        return [dep.get("target_bip") for dep in response["dependencies"] if "target_bip" in dep]
    else:
        return []


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
