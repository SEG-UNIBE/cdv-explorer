import os
import re
import json
import sys
from typing import Any, Dict, List, Optional
from collections import OrderedDict
from tqdm import tqdm
from analysis.conformity.compliance import (
    add_missing_optional_fields as conformity_add_missing_optional_fields,
    assess_compliance as conformity_assess_compliance,
    calculate_compliance_score as conformity_calculate_compliance_score,
    check_headlines as conformity_check_headlines,
    check_required_fields as conformity_check_required_fields,
)
from analysis.classification.preprocess import normalize_classification_fields
from ecosystem_config import ACTIVE_ECOSYSTEM


PREAMBLE_CONFIG = ACTIVE_ECOSYSTEM["preamble"]
REQUIRED_FIELDS = PREAMBLE_CONFIG["required_fields"]
OPTIONAL_FIELDS = PREAMBLE_CONFIG["optional_fields"]
FIELD_ALIASES = PREAMBLE_CONFIG.get("field_aliases", {})
EXPECTED_HEADLINES = PREAMBLE_CONFIG["expected_headlines"]
LIST_VALUED_FIELDS = set(PREAMBLE_CONFIG.get("list_valued_fields", []))

def _extract_raw_preamble_block(file_content: str) -> str:
    """
    Extract the raw preamble block from either legacy <pre> markup or a top-level fenced code block.
    """
    pre_block_pattern = re.compile(r'<pre>(.*?)</pre>', re.DOTALL | re.IGNORECASE)
    pre_block_match = pre_block_pattern.search(file_content)
    if pre_block_match:
        return pre_block_match.group(1)

    fenced_block_pattern = re.compile(r'^\s*```[^\n]*\n(.*?)\n```\s*(?:\n|$)', re.DOTALL)
    fenced_block_match = fenced_block_pattern.search(file_content)
    if fenced_block_match:
        return fenced_block_match.group(1)

    return ""


def extract_preamble_from_pre_block(file_content: str) -> Dict[str, str]:
    """
    Extract the RFC-822 style preamble from either a legacy <pre> block or a fenced markdown block.
    """
    pre_block = _extract_raw_preamble_block(file_content)
    if not pre_block:
        return {}

    preamble = {}
    preamble_pattern = re.compile(r'^\s{0,2}(\w+(?:-\w+)*):\s*(.*)')
    lines = pre_block.splitlines()
    idx = 0

    current_key = None
    current_value = ''

    while idx < len(lines):
        line = lines[idx]
        match = preamble_pattern.match(line)
        if match:
            # If there is already a key-value pair in progress, save it
            if current_key:
                preamble[current_key] = format_value(current_key, current_value)

            # Start a new key-value pair
            current_key = match.group(1).strip().lower().replace('-', '_')
            current_value = match.group(2).strip()
        else:
            # Continuation of a multi-line value
            if current_key and (line.startswith(' ' * 4) or line.startswith('\t')):
                current_value += '\n' + line.strip()

        idx += 1

    # Save the last key-value pair
    if current_key:
        preamble[current_key] = format_value(current_key, current_value)

    return preamble


def format_value(key: str, value: str):
    """
    Formats the value based on the key. For multi-line values (e.g., 'author'),
    returns them as a list. Otherwise, returns the string value.
    """
    if key in LIST_VALUED_FIELDS:  # Convert configured multi-line fields to a list
        return [line.strip() for line in value.split('\n') if line.strip()]
    return value.strip()


def normalize_preamble_fields(preamble: Dict[str, str]) -> Dict[str, str]:
    """Normalize source-specific preamble keys to canonical keys used across the pipeline."""
    normalized = dict(preamble)

    for source_key, canonical_key in FIELD_ALIASES.items():
        if canonical_key in normalized:
            continue
        if source_key not in normalized:
            continue
        normalized[canonical_key] = normalized[source_key]

    normalized = normalize_classification_fields(normalized)

    # Ensure author/license remain list-valued even when aliases provided a scalar.
    for list_field in LIST_VALUED_FIELDS:
        value = normalized.get(list_field)
        if value is None:
            continue
        if isinstance(value, list):
            continue
        normalized[list_field] = [part.strip() for part in str(value).split("\n") if part.strip()]

    return normalized


def check_required_fields(preamble: Dict[str, str], _file_name: str) -> List[str]:
    """
    Return list of missing required fields.
    """
    return conformity_check_required_fields(preamble, REQUIRED_FIELDS)

def check_headlines(file_content: str, _file_name: str) -> List[str]:
    """
    Return list of missing or incorrect headline entries.
    """
    return conformity_check_headlines(file_content, EXPECTED_HEADLINES)

def calculate_compliance_score(preamble: Dict[str, str], file_content: str, _file_name: str) -> float:
    """
    Calculates a compliance score based on missing required fields and incorrect/missing headings.
    """
    return conformity_calculate_compliance_score(
        preamble,
        file_content,
        required_fields=REQUIRED_FIELDS,
        expected_headlines=EXPECTED_HEADLINES,
    )


def assess_compliance(preamble: Dict[str, Any], file_content: str, _file_name: str) -> Dict[str, Any]:
    """
    Builds the structured compliance payload used by downstream analysis artifacts.
    """
    compliance = conformity_assess_compliance(
        preamble,
        file_content,
        required_fields=REQUIRED_FIELDS,
        expected_headlines=EXPECTED_HEADLINES,
    )
    preamble["Compliance Score"] = compliance["score"]
    return compliance


def add_missing_optional_fields(preamble: Dict[str, str]):
    """
    Adds missing optional fields to the preamble with a default value of None (null in JSON).
    """
    conformity_add_missing_optional_fields(preamble, OPTIONAL_FIELDS)


def save_preamble_to_json(
    preamble: Dict[str, str],
    output_dir: str,
    _file_name: str,
    file_prefix: str = "bip",
    id_field: str = "bip",
    compliance_payload: Optional[Dict[str, Any]] = None,
):
    """
    Saves the given preamble to a JSON file in the specified output directory.
    The preamble is saved under a "raw" section in the JSON, with a "preamble" subsection.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Determine the proposal number and format it with leading zeros (e.g., '0002').
    proposal_number = str(preamble.get(id_field, f"unknown_{file_prefix}"))
    proposal_number_str = f"{int(proposal_number):04d}" if proposal_number.isdigit() else f"unknown_{file_prefix}"
    json_file_name = f"{file_prefix}-{proposal_number_str}.json"
    output_path = os.path.join(output_dir, json_file_name)
    existing_json: Dict[str, Any] = {}

    if os.path.exists(output_path):
        try:
            with open(output_path, 'r', encoding='utf-8') as json_file:
                loaded_json = json.load(json_file)
            if isinstance(loaded_json, dict):
                existing_json = loaded_json
        except (json.JSONDecodeError, OSError):
            existing_json = {}

    # Order the keys (required fields first, then optional fields)
    ordered_preamble = OrderedDict()
    for field in REQUIRED_FIELDS + OPTIONAL_FIELDS:
        ordered_preamble[field] = preamble.get(field, None)

    # Structure the JSON data with stable top-level key order.
    json_data = {
        "raw": {
            "preamble": ordered_preamble,
            # Add other sections to "raw" here in the future
        },
        "metadata": {
            "last_commit": None,
            "total_commits": None,
            "metadata_last_updated": None,
            "git_history": [],
            "contributors": None,
        },
        "compliance": compliance_payload or {},
    }

    existing_metadata = existing_json.get("metadata")
    if isinstance(existing_metadata, dict):
        json_data["metadata"].update(existing_metadata)

    existing_insights = existing_json.get("insights")
    if isinstance(existing_insights, dict):
        json_data["insights"] = existing_insights

    for key, value in existing_json.items():
        if key not in json_data:
            json_data[key] = value

    # Save the JSON data to a file
    with open(output_path, 'w', encoding='utf-8') as json_file:
        json.dump(json_data, json_file, ensure_ascii=False, indent=2)

def process_files_and_save_json(
    input_dir: str,
    output_dir: str,
    file_prefix: str = "bip",
    id_field: str = "bip",
    progress_callback=None,
):
    """
    Processes all .mediawiki and .md files in the directory.
    Extracts the preamble and saves it as a JSON file in the specified output directory.
    """
    proposal_files = sorted([f for f in os.listdir(input_dir) if f.endswith(('.mediawiki', '.md'))])
    live_progress = sys.stdout.isatty()
    render_local_progress = progress_callback is None and live_progress
    progress = tqdm(
        proposal_files,
        desc="Preamble extraction",
        unit="ip",
        leave=False,
        position=1,
        dynamic_ncols=render_local_progress,
        file=sys.stdout,
        disable=not render_local_progress,
        mininterval=0.5,
    )
    for proposal_file in progress:
        file_path = os.path.join(input_dir, proposal_file)
        if render_local_progress:
            progress.set_postfix_str(proposal_file, refresh=False)
        if progress_callback is not None:
            progress_callback(proposal_file, 0)

        # Open and read the content of the file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract preamble from the file
        preamble = normalize_preamble_fields(extract_preamble_from_pre_block(content))

        # Check required fields and print the preamble
        check_required_fields(preamble, proposal_file)

        # Add missing optional fields with a default value
        add_missing_optional_fields(preamble)

        # Add structured compliance checks and retain the legacy scalar score.
        compliance_payload = assess_compliance(preamble, content, proposal_file)

        # Save the preamble to a JSON file
        save_preamble_to_json(
            preamble,
            output_dir,
            proposal_file,
            file_prefix=file_prefix,
            id_field=id_field,
            compliance_payload=compliance_payload,
        )
        if progress_callback is not None:
            progress_callback(proposal_file, 1)
    progress.close()
