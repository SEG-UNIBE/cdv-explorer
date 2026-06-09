"""Preamble extractor for RFC-822-style key:value headers (BIPs and similar)."""
import re
import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional

from tqdm import tqdm

from analysis.conformity.compliance import (
    add_missing_optional_fields as _add_missing_optional,
    build_compliance_payload,
    check_required_fields as _check_required,
)
from pipeline.preprocess.checkers import get_checker
from analysis.classification.preprocess import normalize_classification_fields
from analysis.proposal_schema import normalize_proposal_document


def _extract_raw_preamble_block(file_content: str) -> str:
    pre_match = re.search(r"<pre>(.*?)</pre>", file_content, re.DOTALL | re.IGNORECASE)
    fenced_match = re.search(r"^\s*```[^\n]*\n(.*?)\n```\s*(?:\n|$)", file_content, re.DOTALL)
    if not fenced_match:
        fenced_match = re.search(r"```[^\n]*\n(.*?)\n```", file_content, re.DOTALL)
    matches = [match for match in (pre_match, fenced_match) if match]
    if matches:
        return min(matches, key=lambda match: match.start()).group(1)
    return ""


def _extract_preamble(file_content: str, list_valued_fields: set) -> Dict[str, Any]:
    block = _extract_raw_preamble_block(file_content)
    if not block:
        return {}

    preamble: Dict[str, Any] = {}
    key_pattern = re.compile(r"^\s{0,2}(\w+(?:-\w+)*):\s*(.*)")
    current_key: str | None = None
    current_value = ""

    for line in block.splitlines():
        match = key_pattern.match(line)
        if match:
            if current_key:
                preamble[current_key] = _format_value(current_key, current_value, list_valued_fields)
            current_key = match.group(1).strip().lower().replace("-", "_")
            current_value = match.group(2).strip()
        elif current_key and (line.startswith("    ") or line.startswith("\t")):
            current_value += "\n" + line.strip()

    if current_key:
        preamble[current_key] = _format_value(current_key, current_value, list_valued_fields)

    return preamble


def _format_value(key: str, value: str, list_valued_fields: set) -> Any:
    if key in list_valued_fields:
        return [line.strip() for line in value.split("\n") if line.strip()]
    return value.strip()


def _normalize_preamble(
    preamble: Dict[str, Any],
    field_aliases: dict,
    list_valued_fields: set,
) -> Dict[str, Any]:
    normalized = dict(preamble)
    for src_key, canonical_key in field_aliases.items():
        if canonical_key in normalized or src_key not in normalized:
            continue
        normalized[canonical_key] = normalized[src_key]
    normalized = normalize_classification_fields(normalized)
    for list_field in list_valued_fields:
        value = normalized.get(list_field)
        if value is None or isinstance(value, list):
            continue
        normalized[list_field] = [part.strip() for part in str(value).split("\n") if part.strip()]
    return normalized


def _normalize_prefixed_numeric_id(value: Any, file_prefix: str) -> str:
    text = str(value or "").strip()
    match = re.fullmatch(rf"(?i)(?:{re.escape(file_prefix)}[-\s]*)?0*(\d+)", text)
    return str(int(match.group(1))) if match else text


def _save_json(
    preamble: Dict[str, Any],
    output_dir: Path,
    file_prefix: str,
    id_field: str,
    required_fields: List[str],
    optional_fields: List[str],
    compliance_payload: Optional[Dict[str, Any]],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    proposal_number = str(preamble.get(id_field, f"unknown_{file_prefix}"))
    try:
        num_str = f"{int(proposal_number):04d}"
    except (ValueError, TypeError):
        num_str = f"unknown_{file_prefix}"
    json_filename = f"{file_prefix}-{num_str}.json"
    output_path = output_dir / json_filename

    existing: Dict[str, Any] = {}
    if output_path.exists():
        try:
            existing = normalize_proposal_document(json.loads(output_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            existing = {}

    ordered_preamble = OrderedDict()
    for field in required_fields + optional_fields:
        ordered_preamble[field] = preamble.get(field)

    json_data = normalize_proposal_document(existing)
    json_data["raw"]["preamble"] = ordered_preamble
    json_data["insights"]["formal_compliance"] = compliance_payload or {}

    for key, value in existing.items():
        if key not in json_data:
            json_data[key] = value

    output_path.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def extract(
    src_config: dict,
    harvest_dir: Path,
    output_dir: Path,
    progress_callback=None,
) -> None:
    """Extract RFC-822 preambles from all proposal files and write per-proposal JSON."""
    preamble_config = src_config["preamble"]
    required_fields: List[str] = preamble_config["required_fields"]
    optional_fields: List[str] = preamble_config["optional_fields"]
    field_aliases: dict = preamble_config.get("field_aliases", {})
    list_valued_fields: set = set(preamble_config.get("list_valued_fields", []))
    file_prefix: str = src_config["document_prefix"]
    id_field: str = src_config["primary_id_field"]
    document_file_pattern = re.compile(src_config["document_file_pattern"], re.IGNORECASE)

    proposal_files = sorted(
        p for p in harvest_dir.iterdir()
        if p.is_file() and document_file_pattern.match(p.name)
    )

    live = sys.stdout.isatty()
    local_progress = progress_callback is None and live
    progress = tqdm(
        proposal_files,
        desc="Preamble extraction",
        unit="ip",
        leave=False,
        position=1,
        dynamic_ncols=local_progress,
        file=sys.stdout,
        disable=not local_progress,
        mininterval=0.5,
    )

    written_paths: set[Path] = set()

    for proposal_file in progress:
        if local_progress:
            progress.set_postfix_str(proposal_file.name, refresh=False)
        if progress_callback is not None:
            progress_callback(proposal_file.name, 0)

        content = proposal_file.read_text(encoding="utf-8")
        preamble = _normalize_preamble(
            _extract_preamble(content, list_valued_fields),
            field_aliases,
            list_valued_fields,
        )
        if preamble.get(id_field) is not None:
            preamble[id_field] = _normalize_prefixed_numeric_id(preamble.get(id_field), file_prefix)
        _check_required(preamble, required_fields)
        _add_missing_optional(preamble, optional_fields)
        checker = get_checker(src_config.get("compliance_checker", "bip"))
        compliance_payload = build_compliance_payload(checker(preamble, content, src_config))
        preamble["Compliance Score"] = compliance_payload["score"]
        written_paths.add(_save_json(
            preamble, output_dir, file_prefix, id_field,
            required_fields, optional_fields, compliance_payload,
        ))

        if progress_callback is not None:
            progress_callback(proposal_file.name, 1)

    progress.close()

    for stale_path in output_dir.glob(f"{file_prefix}-*.json"):
        if stale_path not in written_paths:
            stale_path.unlink()
