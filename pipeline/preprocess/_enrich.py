"""Shared enrichment stage: git metadata, word list, and dependency extraction."""

import json
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from tqdm import tqdm

from analysis.authorship.mining import update_metadata_from_git
from analysis.dependencies.constants import (
    BODY_EXTRACTED_LLM,
    BODY_EXTRACTED_REGEX,
    PREAMBLE_EXTRACTED,
)
from analysis.dependencies.mining import (
    build_llm_semantic_dependency_manifest_record,
    create_explicit_dependency_targets,
    create_reference_targets,
    llm_extract_semantic_dependencies,
    load_api_key,
    prepare_llm_dependency_text,
)
from analysis.dependencies.utils import normalize_reference_id_for_config
from analysis.evolution import extract_status_timeline
from analysis.proposal_schema import (
    LLM_RUN_STATUS_API_ERROR,
    LLM_RUN_STATUS_SUCCESS,
    is_llm_runs_format,
    normalize_proposal_document,
)
from pipeline.source_context import SourceContext

MIN_WORD_OCCURRENCE = 2
LLM_MAX_CONCURRENCY = 3


def _preserved_llm_runs(
    raw_llm: Any, llm_model: str | None, replace_model_runs: bool
) -> list[dict[str, Any]]:
    runs = list(raw_llm) if is_llm_runs_format(raw_llm) else []
    if not replace_model_runs or not llm_model:
        return runs
    return [run for run in runs if str(run.get("model") or "").strip() != llm_model]


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


def _build_word_list(raw_content: str, stop_words: set[str]) -> dict[str, int]:
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


def _self_targets(
    preamble: dict,
    id_field: str,
    proposal_number: str,
    source_context: SourceContext,
) -> set[str]:
    raw_proposal_id = str(preamble.get(id_field, "")).strip()
    source_slug = str(source_context.source_slug or "")
    reference_config = {
        "proposal_label": source_context.proposal_label,
        "reference_pattern": source_context.reference_pattern,
        "max_proposal_id": source_context.max_proposal_id,
    }
    targets = {f"{source_slug}:{proposal_number}"}
    if raw_proposal_id:
        targets.add(f"{source_slug}:{raw_proposal_id}")
        canonical_id = normalize_reference_id_for_config(
            raw_proposal_id, reference_config
        )
        if canonical_id is not None:
            targets.add(f"{source_slug}:{canonical_id}")
    return targets


def _build_base_insights(
    json_data: dict[str, Any],
    source_file: Path,
    stop_words: set[str],
    proposal_label: str,
    id_field: str,
    reference_pattern: str,
    source_context: SourceContext,
) -> tuple[dict[str, Any], str, str]:
    raw_content = (
        source_file.read_text(encoding="utf-8") if source_file.exists() else ""
    )
    body_content = prepare_llm_dependency_text(raw_content)
    preamble = json_data.get("raw", {}).get("preamble", {})
    proposal_number = _proposal_number(preamble, id_field)

    references = create_reference_targets(
        body_content,
        proposal_label=proposal_label,
        reference_pattern=reference_pattern,
        source_context=source_context,
    )
    explicit_deps = create_explicit_dependency_targets(
        preamble,
        proposal_label=proposal_label,
        source_context=source_context,
    )

    self_targets = _self_targets(preamble, id_field, proposal_number, source_context)

    return (
        {
            "word_list": _build_word_list(raw_content, stop_words),
            "interrelations": {
                PREAMBLE_EXTRACTED: [
                    entry
                    for entry in explicit_deps
                    if entry.get("target") not in self_targets
                ],
                BODY_EXTRACTED_REGEX: [
                    entry
                    for entry in references
                    if entry.get("target") not in self_targets
                ],
            },
        },
        body_content,
        proposal_number,
    )


def _in_focus(proposal_number: str, raw_id: str, focus: set[str]) -> bool:
    return (
        proposal_number in focus
        or raw_id in focus
        or proposal_number.upper() in focus
        or raw_id.upper() in focus
    )


def _append_llm_manifest_run(manifest_path: Path, entry: dict[str, Any]) -> None:
    if manifest_path.exists():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = {}

    runs = payload.get("runs")
    if not isinstance(runs, list):
        runs = []

    run_id = str(entry.get("run_id") or "").strip()
    runs = [
        run
        for run in runs
        if not (
            isinstance(run, dict)
            and str(run.get("run_id") or "").strip()
            and str(run.get("run_id") or "").strip() == run_id
        )
    ]
    runs.append(entry)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps({"schema_version": 1, "runs": runs}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def enrich(
    src_config: dict,
    preprocess_dir: Path,
    harvest_dir: Path,
    analysis_snapshot_dir: Path | None = None,
    skip_llm: bool = False,
    focus: set[str] | None = None,
    replace_llm_model_runs: bool = False,
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
    pending: dict[object, dict[str, Any]] = {}
    submitted_llm = 0
    completed_llm = 0

    executor = ThreadPoolExecutor(max_workers=max_workers) if llm_enabled else None
    llm_run_id = ""
    llm_run_created_at = ""
    if llm_enabled:
        llm_run_created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        llm_run_id = (
            f"{llm_run_created_at}_{str(llm_model or '').strip()}_{uuid4().hex[:8]}"
        )
        if analysis_snapshot_dir is not None:
            manifest_path = (
                analysis_snapshot_dir / f"{src_config['document_prefix']}_llm_runs.json"
            )
            _append_llm_manifest_run(
                manifest_path,
                build_llm_semantic_dependency_manifest_record(
                    run_id=llm_run_id,
                    model=str(llm_model or "").strip(),
                    source_context=source_context,
                    created_at=llm_run_created_at,
                    focus=sorted(focus) if focus else [],
                ),
            )
    llm_bar = (
        tqdm(
            total=0,
            desc="  ↳ LLM",
            unit="ip",
            position=1,
            leave=False,
            dynamic_ncols=True,
            file=sys.stdout,
            mininterval=0.1,
        )
        if (llm_enabled and progress_callback is not None)
        else None
    )

    def _write(output_path: Path, data: dict[str, Any], msg: str) -> None:
        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
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
            print(
                f"WARNING: LLM extraction failed for {record['job_id']}: {exc}",
                file=sys.stderr,
            )
            result = {
                "status": LLM_RUN_STATUS_API_ERROR,
                "findings": [],
                "error_message": str(exc),
            }
        if result.get("status") != LLM_RUN_STATUS_SUCCESS:
            message = str(result.get("error_message") or "").strip()
            suffix = f": {message}" if message else ""
            print(
                f"WARNING: LLM semantic extraction for {record['job_id']} finished with "
                f"status `{result.get('status')}`{suffix}",
                file=sys.stderr,
            )
        data = record["json_data"]
        prior_runs = record.get("preserved_runs") or []
        run_entry = {
            "run_id": llm_run_id,
            "model": llm_model,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": str(result.get("status") or ""),
            "findings": (
                list(result.get("findings") or [])
                if isinstance(result.get("findings"), list)
                else []
            ),
        }
        error_message = str(result.get("error_message") or "").strip()
        if error_message:
            run_entry["error_message"] = error_message
        data["insights"]["interrelations"][BODY_EXTRACTED_LLM] = prior_runs + [
            run_entry
        ]
        completed_llm += 1
        if llm_bar is not None:
            llm_bar.update(1)
        _write(
            record["output_path"],
            data,
            f"{record['job_id']} | LLM {completed_llm}/{submitted_llm}",
        )

    try:
        for json_file in json_files:
            if local_progress:
                progress.set_postfix_str(json_file.name, refresh=False)
            if progress_callback is not None:
                progress_callback(json_file.name, 0)

            raw_json = json.loads(json_file.read_text(encoding="utf-8"))
            raw_llm = (
                raw_json.get("insights", {})
                .get("interrelations", {})
                .get(BODY_EXTRACTED_LLM, [])
            )
            preserved_runs = _preserved_llm_runs(
                raw_llm, llm_model, replace_llm_model_runs
            )
            json_data = normalize_proposal_document(
                raw_json, source_context=source_context
            )
            preamble = json_data.get("raw", {}).get("preamble", {})
            id_value = str(preamble.get(id_field, ""))

            if focus is not None and not _in_focus(
                _proposal_number(preamble, id_field), id_value, focus
            ):
                if progress_callback is not None:
                    progress_callback(json_file.name, 1)
                if local_progress:
                    progress.update(1)
                continue

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
            json_data["insights"]["interrelations"].update(
                base_insights["interrelations"]
            )

            output_path = preprocess_dir / json_file.name

            if not llm_enabled or executor is None:
                json_data["insights"]["interrelations"][BODY_EXTRACTED_LLM] = (
                    preserved_runs
                )
                _write(output_path, json_data, output_path.name)
                continue

            future = executor.submit(
                llm_extract_semantic_dependencies,
                text=llm_content,
                current_proposal_number=proposal_number,
                api_key=api_key,
                model=llm_model,
                source_context=source_context,
            )
            pending[future] = {
                "job_id": json_file.name,
                "json_data": json_data,
                "output_path": output_path,
                "preserved_runs": preserved_runs,
            }
            submitted_llm += 1
            if llm_bar is not None:
                llm_bar.total = submitted_llm
                llm_bar.refresh()

            if len(pending) >= max_workers:
                _complete_future(next(as_completed(tuple(pending.keys()))))

        if llm_enabled:
            for future in as_completed(tuple(pending.keys())):
                _complete_future(future)

    finally:
        if executor is not None:
            executor.shutdown(wait=True)
        if llm_bar is not None:
            llm_bar.close()
        progress.close()
