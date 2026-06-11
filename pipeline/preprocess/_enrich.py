"""Shared enrichment stage: git metadata, word list, and dependency extraction."""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Tuple

from tqdm import tqdm

from analysis.authorship.mining import update_metadata_from_git
from analysis.dependencies.constants import (
    BODY_EXTRACTED_LLM,
    BODY_EXTRACTED_REGEX,
    PREAMBLE_EXTRACTED,
)
from analysis.dependencies.mining import (
    create_explicit_dependency_list,
    create_reference_list,
    llm_extract_implicit_dependencies,
    load_api_key,
    prepare_llm_dependency_text,
)
from analysis.evolution import extract_status_timeline
from analysis.proposal_schema import normalize_proposal_document
from pipeline.source_context import SourceContext

MIN_WORD_OCCURRENCE = 2
LLM_MAX_CONCURRENCY = 5


def _load_stop_words(path_value: str | None) -> set[str]:
    if not path_value:
        return set()
    path = Path(path_value)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent.parent / path
    if not path.exists():
        raise FileNotFoundError(f"Stop words file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return {
            line.strip().lower()
            for line in handle
            if line.strip() and not line.lstrip().startswith("#")
        }


def _build_word_list(raw_content: str, stop_words: set[str]) -> Dict[str, int]:
    if not raw_content:
        return {}
    words = re.findall(r"\b\w+\b", raw_content.lower())
    counts = Counter(w for w in words if w not in stop_words)
    return {w: c for w, c in counts.most_common() if c >= MIN_WORD_OCCURRENCE}


def _find_source_file(repo_dir: Path, id_value: str, src_config: dict) -> Path | None:
    """Locate the raw proposal file for a given ID in the harvested repo."""
    prefix = src_config["document_prefix"]

    # BIP-style: {prefix}-{padded}.md/.mediawiki/.rst
    if id_value.isdigit():
        padded = id_value.zfill(4)
        for ext in (".mediawiki", ".md", ".rst"):
            candidate = repo_dir / f"{prefix}-{padded}{ext}"
            if candidate.exists():
                return candidate

    # NIP-style: bare {id}.md (the stem equals the stored id)
    for ext in (".md", ".mediawiki", ".rst"):
        candidate = repo_dir / f"{id_value}{ext}"
        if candidate.exists():
            return candidate
        # Also try case-insensitive variants (e.g. 5a.md vs 5A.md)
        candidate_lower = repo_dir / f"{id_value.lower()}{ext}"
        if candidate_lower.exists():
            return candidate_lower

    return None


def _proposal_number(preamble: dict, id_field: str) -> str:
    """Return the proposal's self-reference string suitable for ref filtering."""
    raw = str(preamble.get(id_field, ""))
    try:
        return str(int(raw))
    except ValueError:
        return raw


def _build_base_insights(
    json_data: Dict[str, Any],
    source_file: Path,
    stop_words: set[str],
    proposal_label: str,
    id_field: str,
    reference_pattern: str,
    source_context: SourceContext,
) -> Tuple[Dict[str, Any], str, str]:
    raw_content = source_file.read_text(encoding="utf-8") if source_file.exists() else ""
    body_content = prepare_llm_dependency_text(raw_content)
    preamble = json_data.get("raw", {}).get("preamble", {})
    proposal_number = _proposal_number(preamble, id_field)

    references = create_reference_list(
        body_content,
        proposal_label=proposal_label,
        reference_pattern=reference_pattern,
        source_context=source_context,
    )
    explicit_deps = create_explicit_dependency_list(
        preamble,
        proposal_label=proposal_label,
        source_context=source_context,
    )

    raw_proposal_id = str(preamble.get(id_field, "")).strip()
    self_refs = {f"{proposal_label} {proposal_number}"}
    if raw_proposal_id:
        self_refs.add(f"{proposal_label} {raw_proposal_id.upper()}")
        if proposal_label.upper() == "NIP":
            self_refs.add(f"{proposal_label} {raw_proposal_id.upper().zfill(2)}")
    return (
        {
            "word_list": _build_word_list(raw_content, stop_words),
            "interrelations": {
                PREAMBLE_EXTRACTED: [r for r in explicit_deps if r not in self_refs],
                BODY_EXTRACTED_REGEX: [r for r in references if r not in self_refs],
            },
        },
        body_content,
        proposal_number,
    )


def enrich(
    src_config: dict,
    preprocess_dir: Path,
    harvest_dir: Path,
    skip_llm: bool = False,
    source_context: SourceContext | None = None,
    progress_callback=None,
) -> None:
    """Enrich all preprocess JSON files with git metadata, word lists, and dependencies."""
    proposal_label: str = src_config["proposal_acronym"]
    id_field: str = src_config["primary_id_field"]
    reference_pattern: str = src_config["reference_pattern"]
    source_context = source_context or SourceContext.from_config(src_config)
    stop_words = _load_stop_words(src_config.get("stop_words_file"))

    json_files = sorted(f for f in preprocess_dir.iterdir() if f.suffix == ".json")

    live = sys.stdout.isatty()
    local_progress = progress_callback is None and live
    progress = tqdm(
        total=len(json_files),
        desc="Metadata and insights",
        unit="ip",
        leave=False,
        position=1,
        dynamic_ncols=local_progress,
        file=sys.stdout,
        disable=not local_progress,
        mininterval=0.5,
    )

    api_key = None if skip_llm else load_api_key()
    llm_model = None if skip_llm else source_context.llm_model
    llm_enabled = bool(api_key and llm_model) and not skip_llm
    if not skip_llm and not api_key:
        print(
            "WARNING: LLM step skipped — no API key found. "
            "Set OPENAI_API_KEY or create apikey.secret.",
            file=sys.stderr,
        )
    if not skip_llm and not llm_model:
        print(
            "WARNING: LLM step skipped — no LLM model configured. "
            "Set llm.model in the ecosystem YAML.",
            file=sys.stderr,
        )

    max_workers = max(1, LLM_MAX_CONCURRENCY)
    pending: Dict[object, Dict[str, Any]] = {}
    submitted_llm = 0
    completed_llm = 0

    executor = ThreadPoolExecutor(max_workers=max_workers) if llm_enabled else None

    def _write(output_path: Path, data: Dict[str, Any], msg: str) -> None:
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        if progress_callback is not None:
            progress_callback(msg, 1)
        if local_progress:
            progress.set_postfix_str(msg, refresh=False)
            progress.update(1)

    def _complete_future(future) -> None:
        nonlocal completed_llm
        record = pending.pop(future)
        try:
            result = future.result()
        except Exception as exc:
            print(f"WARNING: LLM extraction failed for {record['job_id']}: {exc}", file=sys.stderr)
            result = []
        data = record["json_data"]
        data["insights"]["interrelations"][BODY_EXTRACTED_LLM] = result if isinstance(result, list) else []
        completed_llm += 1
        _write(record["output_path"], data, f"{record['job_id']} | LLM {completed_llm}/{submitted_llm}")

    try:
        for json_file in json_files:
            if local_progress:
                progress.set_postfix_str(json_file.name, refresh=False)
            if progress_callback is not None:
                progress_callback(json_file.name, 0)

            json_data = normalize_proposal_document(
                json.loads(json_file.read_text(encoding="utf-8")),
                source_context=source_context,
            )
            preamble = json_data.get("raw", {}).get("preamble", {})
            id_value = str(preamble.get(id_field, ""))
            source_file = _find_source_file(harvest_dir, id_value, src_config)

            if not source_file:
                if progress_callback is not None:
                    progress_callback(json_file.name, 1)
                if local_progress:
                    progress.update(1)
                continue

            json_data = update_metadata_from_git(json_data, source_file, harvest_dir)
            json_data["insights"]["changes_in_status"] = extract_status_timeline(
                harvest_dir,
                source_file,
                source_context=source_context,
            )
            base_insights, llm_content, proposal_number = _build_base_insights(
                json_data,
                source_file,
                stop_words,
                proposal_label,
                id_field,
                reference_pattern,
                source_context,
            )
            json_data["insights"]["word_list"] = base_insights["word_list"]
            json_data["insights"]["interrelations"].update(base_insights["interrelations"])

            output_path = preprocess_dir / json_file.name

            if not llm_enabled or executor is None:
                existing_llm = json_data["insights"]["interrelations"].get(BODY_EXTRACTED_LLM)
                json_data["insights"]["interrelations"][BODY_EXTRACTED_LLM] = (
                    existing_llm if isinstance(existing_llm, list) else []
                )
                _write(output_path, json_data, output_path.name)
                continue

            future = executor.submit(
                llm_extract_implicit_dependencies,
                text=llm_content,
                current_proposal_number=proposal_number,
                proposal_label=proposal_label,
                api_key=api_key,
                model=llm_model,
                source_context=source_context,
            )
            pending[future] = {
                "job_id": json_file.name,
                "json_data": json_data,
                "output_path": output_path,
            }
            submitted_llm += 1

            if len(pending) >= max_workers:
                _complete_future(next(as_completed(tuple(pending.keys()))))

        if llm_enabled:
            for future in as_completed(tuple(pending.keys())):
                _complete_future(future)

    finally:
        if executor is not None:
            executor.shutdown(wait=True)
        progress.close()
