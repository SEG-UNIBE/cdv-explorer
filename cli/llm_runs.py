"""Helpers that inspect stored LLM extraction runs in preprocessed snapshot JSON."""

from __future__ import annotations

import json
from pathlib import Path

from analysis.proposal_schema import is_llm_runs_format, is_successful_llm_run


def _existing_llm_model_run_counts(
    preprocess_dir: Path,
    *,
    id_field: str,
    llm_model: str,
    focus: set[str] | None = None,
) -> tuple[int, int]:
    matching_documents = 0
    matching_runs = 0

    for json_file in sorted(preprocess_dir.glob("*.json")):
        raw_json = json.loads(json_file.read_text(encoding="utf-8"))
        preamble = raw_json.get("raw", {}).get("preamble", {})
        raw_id = str(preamble.get(id_field, ""))
        try:
            proposal_number = str(int(raw_id))
        except ValueError:
            proposal_number = raw_id
        if focus is not None:
            in_focus = (
                proposal_number in focus
                or raw_id in focus
                or proposal_number.upper() in focus
                or raw_id.upper() in focus
            )
            if not in_focus:
                continue

        raw_llm = (
            raw_json.get("insights", {})
            .get("interrelations", {})
            .get("body_extracted_llm", [])
        )
        if not is_llm_runs_format(raw_llm):
            continue

        doc_counted = False
        for run in raw_llm:
            if str(run.get("model") or "").strip() != llm_model:
                continue
            matching_runs += 1
            if not doc_counted:
                matching_documents += 1
                doc_counted = True

    return matching_documents, matching_runs


def _failed_llm_model_focus(
    preprocess_dir: Path,
    *,
    id_field: str,
    llm_model: str,
    focus: set[str] | None = None,
) -> set[str]:
    failed_ids: set[str] = set()

    for json_file in sorted(preprocess_dir.glob("*.json")):
        raw_json = json.loads(json_file.read_text(encoding="utf-8"))
        preamble = raw_json.get("raw", {}).get("preamble", {})
        raw_id = str(preamble.get(id_field, ""))
        try:
            proposal_number = str(int(raw_id))
        except ValueError:
            proposal_number = raw_id
        if focus is not None:
            in_focus = (
                proposal_number in focus
                or raw_id in focus
                or proposal_number.upper() in focus
                or raw_id.upper() in focus
            )
            if not in_focus:
                continue

        raw_llm = (
            raw_json.get("insights", {})
            .get("interrelations", {})
            .get("body_extracted_llm", [])
        )
        if not is_llm_runs_format(raw_llm):
            continue

        model_runs = [
            run
            for run in raw_llm
            if str(run.get("model") or "").strip() == llm_model
        ]
        if not model_runs:
            continue

        latest_run = max(model_runs, key=lambda run: str(run.get("timestamp") or ""))
        if is_successful_llm_run(latest_run):
            continue

        failed_ids.add(proposal_number)

    return failed_ids


def _available_llm_models_in_preprocess_dir(preprocess_dir: Path) -> list[str]:
    models: set[str] = set()
    for json_file in sorted(preprocess_dir.glob("*.json")):
        raw_json = json.loads(json_file.read_text(encoding="utf-8"))
        raw_llm = (
            raw_json.get("insights", {})
            .get("interrelations", {})
            .get("body_extracted_llm", [])
        )
        if not is_llm_runs_format(raw_llm):
            continue
        for run in raw_llm:
            model = str(run.get("model") or "").strip()
            if model and is_successful_llm_run(run):
                models.add(model)
    return sorted(models)
