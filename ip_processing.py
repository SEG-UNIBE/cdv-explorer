import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Dict, List, Tuple
from tqdm import tqdm

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
LLM_MAX_CONCURRENCY = 3

# --- Utility Functions ---
def load_bip_content(file_path: Path) -> str:
    try:
        with file_path.open('r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
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


def create_explicit_dependency_list(
    preamble: Dict[str, any],
    proposal_label: str = PROPOSAL_LABEL,
) -> List[str]:
    dependency_fields = ["requires", "replaces", "superseded_by"]
    label = re.escape(proposal_label)
    id_pattern = re.compile(rf"(?i)(?:{label}[-\s]*)?(\d+)")
    dependency_ids = set()

    for field in dependency_fields:
        value = preamble.get(field)
        if not value:
            continue

        raw_items = value if isinstance(value, list) else str(value).split(",")
        for item in raw_items:
            for proposal_id in id_pattern.findall(str(item)):
                dependency_ids.add(f"{proposal_label} {int(proposal_id)}")

    return sorted(dependency_ids)


def llm_extract_implicit_dependencies(
    text,
    current_bip_number=None,
    proposal_label: str = PROPOSAL_LABEL,
    api_key: str | None = None,
):

    prompt = f"""
Analyze {PROPOSAL_SINGULAR} {proposal_label}{f" {current_bip_number}" if current_bip_number else ""}.

Task:
Return only the other {proposal_label}s that this proposal materially depends on.

Dependencies may be explicit or implicit.
Count another {proposal_label} as a dependency when the proposal materially builds on, requires, extends, constrains, amends, specializes, or otherwise substantively relies on concepts, mechanisms, formats, semantics, activation rules, or assumptions introduced by that {proposal_label}, even if the text does not say "depends on" directly.

Do not include:
- mere mentions or citations
- history or background
- comparisons to alternative approaches
- examples
- topical relatedness
- speculation
- self-references

Judge the technical context, not just surface mentions.
Be conservative. If the text does not provide strong evidence that another {proposal_label} is a real dependency, do not include it.

Output requirements:
- Return only a JSON array
- No explanation
- No markdown
- Deduplicate results
- Normalize identifiers to "{proposal_label} N" (for example "{proposal_label}-0016" -> "{proposal_label} 16")
- Exclude {proposal_label} {current_bip_number} if present
- Return [] if there are no real dependencies

Examples:
Text: This proposal depends on {proposal_label} 32 and {proposal_label} 39.
Output: ["{proposal_label} 32", "{proposal_label} 39"]

Text: This proposal builds upon {proposal_label}-0016 for partially signed transactions.
Output: ["{proposal_label} 16"]

Text: Since {proposal_label} 44 introduced a privacy concern, this proposal suggests a new hashing function to address that issue.
Output: []

Text:
\"\"\"{text}\"\"\"
"""
    
    model="gpt-5-nano"
    resolved_api_key = api_key or load_api_key()
    if not resolved_api_key:
        return []

    client = OpenAI(api_key=resolved_api_key)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(response.choices[0].message.content.strip())
    except (JSONDecodeError, TypeError, ValueError, KeyError, OSError, TimeoutError, ConnectionError) as e:
        return []

def load_api_key():
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key

    secret_file = Path("apikey.secret")
    if secret_file.exists():
        with secret_file.open(encoding="utf-8") as f:
            return f.read().strip()

    return None


def extract_implicit_dependencies_parallel(
    llm_jobs: List[Dict[str, str]],
    proposal_label: str = PROPOSAL_LABEL,
    completion_callback=None,
) -> Dict[str, List[str]]:
    if not llm_jobs:
        return {}

    api_key = load_api_key()
    if not api_key:
        return {job["job_id"]: [] for job in llm_jobs}

    total_jobs = len(llm_jobs)
    max_workers = min(max(1, LLM_MAX_CONCURRENCY), total_jobs)
    implicit_dependencies_by_job: Dict[str, List[str]] = {}
    completed_jobs = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                llm_extract_implicit_dependencies,
                job["raw_content"],
                job["proposal_number"],
                proposal_label,
                api_key,
            ): job["job_id"]
            for job in llm_jobs
        }

        for future in as_completed(futures):
            job_id = futures[future]
            try:
                result = future.result()
            except Exception:
                result = []

            implicit_dependencies_by_job[job_id] = result if isinstance(result, list) else []
            completed_jobs += 1

            if completion_callback is not None:
                completion_callback(completed_jobs, total_jobs, max_workers, job_id)

    for job in llm_jobs:
        implicit_dependencies_by_job.setdefault(job["job_id"], [])

    return implicit_dependencies_by_job


def build_base_insights(
    json_data: Dict[str, any],
    bip_file_path: Path,
    proposal_label: str = PROPOSAL_LABEL,
    id_field: str = PRIMARY_ID_FIELD,
) -> Tuple[Dict[str, any], str, str]:
    raw_content = load_bip_content(bip_file_path)
    preamble = json_data.get("raw", {}).get("preamble", {})
    references = create_reference_list(raw_content, proposal_label=proposal_label)
    explicit_dependencies = create_explicit_dependency_list(preamble, proposal_label=proposal_label)
    proposal_number = str(int(json_data["raw"]["preamble"][id_field]))

    filtered_references = [
        proposal for proposal in references if proposal != f"{proposal_label} {proposal_number}"
    ]
    filtered_explicit_dependencies = [
        proposal for proposal in explicit_dependencies if proposal != f"{proposal_label} {proposal_number}"
    ]

    return (
        {
            "word_list": create_word_list(raw_content),
            "explicit_references": filtered_references,
            "explicit_dependencies": filtered_explicit_dependencies,
        },
        raw_content,
        proposal_number,
    )

def process_ip_files(
    input_dir: Path,
    output_dir: Path,
    repo_dir: Path,
    file_prefix: str = DOCUMENT_PREFIX,
    proposal_label: str = PROPOSAL_LABEL,
    id_field: str = PRIMARY_ID_FIELD,
    progress_callback=None,
):
    """Process all BIP JSON files and update metadata & insights."""
    json_files = sorted([f for f in input_dir.iterdir() if f.suffix == '.json'])
    live_progress = sys.stdout.isatty()
    render_local_progress = progress_callback is None and live_progress
    progress = tqdm(
        total=len(json_files),
        desc="Metadata and insights",
        unit="ip",
        leave=False,
        position=1,
        dynamic_ncols=render_local_progress,
        file=sys.stdout,
        disable=not render_local_progress,
        mininterval=0.5,
    )
    prepared_records = []
    llm_jobs: List[Dict[str, str]] = []

    for json_file in json_files:
        if render_local_progress:
            progress.set_postfix_str(json_file.name, refresh=False)
        if progress_callback is not None:
            progress_callback(json_file.name, 0)
        with json_file.open('r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        preamble = json_data.get("raw", {}).get("preamble", {})
        bip_number = str(preamble.get(id_field, "")).zfill(4)
        bip_file_path = find_bip_file(repo_dir, bip_number, file_prefix=file_prefix)
        
        if not bip_file_path:
            if progress_callback is not None:
                progress_callback(json_file.name, 1)
            if render_local_progress:
                progress.update(1)
            continue
        
        json_data = update_metadata(json_data, bip_file_path, repo_dir)

        base_insights, raw_content, proposal_number = build_base_insights(
            json_data,
            bip_file_path,
            proposal_label=proposal_label,
            id_field=id_field,
        )
        json_data.setdefault("insights", {})
        json_data["insights"].update(base_insights)

        job_id = json_file.name
        llm_jobs.append(
            {
                "job_id": job_id,
                "raw_content": raw_content,
                "proposal_number": proposal_number,
            }
        )
        prepared_records.append(
            {
                "job_id": job_id,
                "json_data": json_data,
                "output_path": output_dir / json_file.name,
            }
        )

    if render_local_progress and llm_jobs:
        progress.set_postfix_str(
            f"LLM dependencies (parallel, max={min(max(1, LLM_MAX_CONCURRENCY), len(llm_jobs))})",
            refresh=False,
        )

    llm_progress = None
    if render_local_progress and llm_jobs:
        worker_count = min(max(1, LLM_MAX_CONCURRENCY), len(llm_jobs))
        llm_progress = tqdm(
            total=len(llm_jobs),
            desc=f"LLM dependencies ({worker_count} workers)",
            unit="ip",
            leave=False,
            position=2,
            dynamic_ncols=render_local_progress,
            file=sys.stdout,
            disable=not render_local_progress,
            mininterval=0.2,
        )

    def on_llm_job_completion(
        completed_jobs: int,
        total_jobs: int,
        worker_count: int,
        job_id: str,
    ):
        message = f"LLM jobs {completed_jobs}/{total_jobs}"

        if llm_progress is not None:
            llm_progress.update(completed_jobs - llm_progress.n)
            llm_progress.set_postfix_str(message, refresh=False)

        if render_local_progress:
            progress.set_postfix_str(message, refresh=False)

        should_emit_status = completed_jobs == total_jobs or completed_jobs % worker_count == 0
        if progress_callback is not None and should_emit_status:
            progress_callback(f"{message} (latest: {job_id})", 0)

    implicit_dependencies_by_job = extract_implicit_dependencies_parallel(
        llm_jobs,
        proposal_label=proposal_label,
        completion_callback=on_llm_job_completion,
    )

    if llm_progress is not None:
        llm_progress.close()

    for record in prepared_records:
        json_data = record["json_data"]
        job_id = record["job_id"]
        json_data.setdefault("insights", {})
        json_data["insights"]["implicit_dependencies"] = implicit_dependencies_by_job.get(job_id, [])

        output_path = record["output_path"]
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        if progress_callback is not None:
            progress_callback(output_path.name, 1)
        if render_local_progress:
            progress.update(1)

    progress.close()
