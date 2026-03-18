import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple
from tqdm import tqdm

from analysis.authorship.mining import update_metadata_from_git
from analysis.dependencies.mining import (
    create_explicit_dependency_list,
    create_reference_list,
    llm_extract_implicit_dependencies,
    load_api_key,
)
from ecosystem_config import ACTIVE_ECOSYSTEM

PROPOSAL_LABEL = ACTIVE_ECOSYSTEM["proposal_acronym"]
PRIMARY_ID_FIELD = ACTIVE_ECOSYSTEM["primary_id_field"]
DOCUMENT_PREFIX = ACTIVE_ECOSYSTEM["document_prefix"]
STOP_WORDS_FILE = ACTIVE_ECOSYSTEM.get("stop_words_file")
MIN_WORD_OCCURRENCE = 2

LLM_MAX_CONCURRENCY = 5


def load_stop_words(path_value: str | None) -> set[str]:
    if not path_value:
        return set()

    path = Path(path_value)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path

    if not path.exists():
        raise FileNotFoundError(f"Stop words file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        return {
            line.strip().lower()
            for line in handle
            if line.strip() and not line.lstrip().startswith("#")
        }


STOP_WORDS = load_stop_words(STOP_WORDS_FILE)

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

def build_word_list(raw_content: str) -> Dict[str, int]:
    if not raw_content:
        return {}

    words = re.findall(r"\b\w+\b", raw_content.lower())
    filtered_words = [word for word in words if word not in STOP_WORDS]
    counts = Counter(filtered_words)
    return {
        word: count
        for word, count in counts.most_common()
        if count >= MIN_WORD_OCCURRENCE
    }


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
            "word_list": build_word_list(raw_content),
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
    skip_llm: bool = False,
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
    api_key = None if skip_llm else load_api_key()
    max_workers = max(1, LLM_MAX_CONCURRENCY)
    llm_enabled = bool(api_key) and not skip_llm
    pending_futures: Dict[object, Dict[str, any]] = {}
    submitted_llm_jobs = 0
    completed_llm_jobs = 0

    if render_local_progress and llm_enabled:
        progress.set_postfix_str(
            f"LLM dependencies (rolling, max={max_workers})",
            refresh=False,
        )

    executor = ThreadPoolExecutor(max_workers=max_workers) if llm_enabled else None

    def write_record(output_path: Path, json_data: Dict[str, any], status_message: str) -> None:
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        if progress_callback is not None:
            progress_callback(status_message, 1)
        if render_local_progress:
            progress.set_postfix_str(status_message, refresh=False)
            progress.update(1)

    def complete_one_future(future) -> None:
        nonlocal completed_llm_jobs
        record = pending_futures.pop(future)
        try:
            result = future.result()
        except Exception:
            result = []

        implicit_dependencies = result if isinstance(result, list) else []
        json_data = record["json_data"]
        json_data.setdefault("insights", {})
        json_data["insights"]["implicit_dependencies"] = implicit_dependencies

        completed_llm_jobs += 1
        status_message = (
            f"{record['job_id']} | LLM jobs {completed_llm_jobs}/{submitted_llm_jobs}"
        )
        write_record(record["output_path"], json_data, status_message)

    try:
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

            json_data = update_metadata_from_git(json_data, bip_file_path, repo_dir)
            base_insights, raw_content, proposal_number = build_base_insights(
                json_data,
                bip_file_path,
                proposal_label=proposal_label,
                id_field=id_field,
            )
            json_data.setdefault("insights", {})
            json_data["insights"].update(base_insights)

            output_path = output_dir / json_file.name

            if not llm_enabled or executor is None:
                existing_implicit_dependencies = json_data["insights"].get("implicit_dependencies")
                if not isinstance(existing_implicit_dependencies, list):
                    existing_implicit_dependencies = []
                json_data["insights"]["implicit_dependencies"] = existing_implicit_dependencies
                write_record(output_path, json_data, output_path.name)
                continue

            future = executor.submit(
                llm_extract_implicit_dependencies,
                raw_content,
                proposal_number,
                proposal_label,
                api_key,
            )
            pending_futures[future] = {
                "job_id": json_file.name,
                "json_data": json_data,
                "output_path": output_path,
            }
            submitted_llm_jobs += 1

            if len(pending_futures) >= max_workers:
                next_done = next(as_completed(tuple(pending_futures.keys())))
                complete_one_future(next_done)

        if llm_enabled:
            for future in as_completed(tuple(pending_futures.keys())):
                complete_one_future(future)
    finally:
        if executor is not None:
            executor.shutdown(wait=True)
        progress.close()
