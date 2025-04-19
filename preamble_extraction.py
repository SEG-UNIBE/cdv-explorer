import os
import re
import json
from typing import Dict
from collections import OrderedDict

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


def check_required_fields(preamble: Dict[str, str], file_name: str):
    """
    Check if all required BIP fields are present. Log missing required fields as warnings.
    """
    missing_required_fields = [field for field in REQUIRED_FIELDS if field not in preamble]
    if missing_required_fields:
        print(f"Warning: Missing required fields in {file_name}: {missing_required_fields}")

        
def check_headlines(file_content: str, file_name: str):
    """
    Parses Markdown content and checks for:
      - Missing required section headings
      - Extra/unexpected headings
      - Incorrect heading depth (e.g., `#` instead of `##`)
    """
    headline_pattern = re.compile(r'^(#{1,6})\s+(.*)', re.MULTILINE)
    found_headlines = []

    for match in headline_pattern.finditer(file_content):
        hashes, title = match.groups()
        level = len(hashes)
        normalized_title = title.strip().lower()
        found_headlines.append((normalized_title, level))

    # Build lookup
    found_map = {title: level for title, level in found_headlines}

    missing_headlines = []
    extra_headlines = []
    wrong_depth = []

    # Check for missing or mis-leveled expected headlines
    for expected_title, expected_level in EXPECTED_HEADLINES.items():
        if expected_title not in found_map:
            missing_headlines.append(expected_title)
        elif found_map[expected_title] != expected_level:
            wrong_depth.append((expected_title, found_map[expected_title], expected_level))

    # Check for unexpected headlines
    for title, level in found_headlines:
        if title not in EXPECTED_HEADLINES:
            extra_headlines.append(title)

    # Log results
    if missing_headlines:
        print(f"[{file_name}] ❌ Missing required sections: {missing_headlines}")
    if extra_headlines:
        print(f"[{file_name}] ⚠️ Extra/unexpected sections: {extra_headlines}")
    if wrong_depth:
        print(f"[{file_name}] ⚠️ Headings with incorrect depth:")
        for title, actual, expected in wrong_depth:
            print(f"    - '{title}' has level {actual}, expected {expected}")



def add_missing_optional_fields(preamble: Dict[str, str]):
    """
    Adds missing optional fields to the preamble with a default value of None (null in JSON).
    """
    for field in OPTIONAL_FIELDS:
        if field not in preamble:
            preamble[field] = None


def save_preamble_to_json(preamble: Dict[str, str], output_dir: str, file_name: str):
    """
    Saves the given preamble to a JSON file in the specified output directory.
    The preamble is saved under a "raw" section in the JSON, with a "preamble" subsection.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Determine the BIP number and format it with leading zeros (e.g., '0002')
    bip_number = preamble.get('bip', 'unknown_bip')
    bip_number_str = f"{int(bip_number):04d}" if bip_number.isdigit() else 'unknown_bip'
    json_file_name = f"bip-{bip_number_str}.json"
    output_path = os.path.join(output_dir, json_file_name)

    # Order the keys (required fields first, then optional fields)
    ordered_preamble = OrderedDict()
    for field in REQUIRED_FIELDS + OPTIONAL_FIELDS:
        ordered_preamble[field] = preamble.get(field, None)

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


def process_files_and_save_json(input_dir: str, output_dir: str):
    """
    Processes all .mediawiki and .md files in the directory.
    Extracts the preamble and saves it as a JSON file in the specified output directory.
    """
    bip_files = [f for f in os.listdir(input_dir) if f.endswith(('.mediawiki', '.md'))]
    for bip_file in bip_files:
        file_path = os.path.join(input_dir, bip_file)
        print(f"Processing {file_path}")

        # Open and read the content of the file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract preamble from the file
        preamble = extract_preamble_from_pre_block(content)

        # Check required fields and print the preamble
        check_required_fields(preamble, bip_file)

        # Checkk headlines
        check_headlines(content, bip_file)

        # Add missing optional fields with a default value
        add_missing_optional_fields(preamble)

        # Save the preamble to a JSON file
        save_preamble_to_json(preamble, output_dir, bip_file)
