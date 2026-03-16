import os
import re
import json
from typing import Dict, List
from collections import OrderedDict
from analysis.conformity.compliance import (
    add_missing_optional_fields as conformity_add_missing_optional_fields,
    calculate_compliance_score as conformity_calculate_compliance_score,
    check_headlines as conformity_check_headlines,
    check_required_fields as conformity_check_required_fields,
)


# Separate required and optional fields based on your instructions
REQUIRED_FIELDS = [
    'bip', 'title', 'author', 'comments_uri', 'status', 'type', 'created', 'license'
]

OPTIONAL_FIELDS = [
    'layer', 'discussions_to', 'comments_summary', 'license_code', 'post_history',
    'requires', 'replaces', 'superseded_by'
]

EXPECTED_HEADLINES = {
    "abstract": 2,
    "motivation": 2,
    "specification": 2,
    "rationale": 2,
    "backwards compatibility": 2,
    "reference implementation": 2,
    "security considerations": 2,
    "copyright": 2,
    "references": 2,
}


def extract_preamble_from_pre_block(file_content: str) -> Dict[str, str]:
    """
    Extracts the preamble from the content of a file, recognizing the structure inside <pre> blocks
    with lines starting with at least two spaces.
    """
    pre_block_pattern = re.compile(r'<pre>(.*?)</pre>', re.DOTALL)
    pre_block_match = pre_block_pattern.search(file_content)

    if not pre_block_match:
        print("Error: No <pre> block found.")
        return {}

    pre_block = pre_block_match.group(1)
    preamble = {}
    preamble_pattern = re.compile(r'^\s{2}(\w+(?:-\w+)*):\s*(.*)')  # Match fields with at least two spaces at the start
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
            if current_key and line.startswith(' ' * 4):  # Continuation lines have 4 spaces
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
    if key == 'author' or key == 'license':  # Convert multi-line fields to a list
        return [line.strip() for line in value.split('\n') if line.strip()]
    return value.strip()


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
    conformity_calculate_compliance_score(
        preamble,
        file_content,
        required_fields=REQUIRED_FIELDS,
        expected_headlines=EXPECTED_HEADLINES,
    )


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

    # Order the keys (required fields first, then optional fields)
    ordered_preamble = OrderedDict()
    for field in REQUIRED_FIELDS + OPTIONAL_FIELDS:
        ordered_preamble[field] = preamble.get(field, None)
    
    if "Compliance Score" in preamble:
        ordered_preamble["compliance_score"] = preamble["Compliance Score"]

    # Structure the JSON data with a "raw" section
    json_data = {
        "raw": {
            "preamble": ordered_preamble,
            # Add other sections to "raw" here in the future
        }
    }

    # Save the JSON data to a file
    with open(output_path, 'w', encoding='utf-8') as json_file:
        json.dump(json_data, json_file, ensure_ascii=False, indent=2)

    print(f"Saved preamble to {output_path}")


def process_files_and_save_json(
    input_dir: str,
    output_dir: str,
    file_prefix: str = "bip",
    id_field: str = "bip",
):
    """
    Processes all .mediawiki and .md files in the directory.
    Extracts the preamble and saves it as a JSON file in the specified output directory.
    """
    proposal_files = [f for f in os.listdir(input_dir) if f.endswith(('.mediawiki', '.md'))]
    for proposal_file in proposal_files:
        file_path = os.path.join(input_dir, proposal_file)
        print(f"Processing {file_path}")

        # Open and read the content of the file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract preamble from the file
        preamble = extract_preamble_from_pre_block(content)

        # Check required fields and print the preamble
        check_required_fields(preamble, proposal_file)

        # Add missing optional fields with a default value
        add_missing_optional_fields(preamble)

        #Add compliance score
        calculate_compliance_score(preamble, content, proposal_file)

        # Save the preamble to a JSON file
        save_preamble_to_json(
            preamble,
            output_dir,
            proposal_file,
            file_prefix=file_prefix,
            id_field=id_field,
        )
