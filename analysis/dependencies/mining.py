import json
import os
import re
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, List

from openai import OpenAI

from analysis.proposal_schema import get_preamble_interrelations
from pipeline.ecosystem_config import ACTIVE_ECOSYSTEM


PROPOSAL_LABEL = ACTIVE_ECOSYSTEM["proposal_acronym"]
PROPOSAL_SINGULAR = ACTIVE_ECOSYSTEM["proposal_term_singular"]
REFERENCE_PATTERN = ACTIVE_ECOSYSTEM["reference_pattern"]
MAX_PROPOSAL_ID = ACTIVE_ECOSYSTEM.get("max_proposal_id")
LLM_MODEL = "gpt-5"
TOP_PRE_BLOCK_PATTERN = re.compile(r"^\s*<pre>.*?</pre>\s*", re.DOTALL | re.IGNORECASE)
TOP_FENCED_BLOCK_PATTERN = re.compile(r"^\s*```[^\n]*\n.*?\n```\s*(?:\n|$)", re.DOTALL)
STRUCTURED_OUTPUT_NAME = "implicit_dependency_list"
MAX_REFERENCE_DIGITS = 6
REFERENCE_LIST_PATTERN = re.compile(
    rf"(?i)\b{re.escape(PROPOSAL_LABEL)}s?[-#\s]*(\d{{1,{MAX_REFERENCE_DIGITS}}}(?!\d)(?:\s*(?:,|/|and|or)\s*\d{{1,{MAX_REFERENCE_DIGITS}}}(?!\d))*)"
)
HEX_REFERENCE_LIST_PATTERN = re.compile(
    rf"(?i)\b{re.escape(PROPOSAL_LABEL)}s?[-#\s]*([0-9A-Fa-f]{{1,{MAX_REFERENCE_DIGITS}}}(?![0-9A-Fa-f])(?:\s*(?:,|/|and|or)\s*[0-9A-Fa-f]{{1,{MAX_REFERENCE_DIGITS}}}(?![0-9A-Fa-f]))*)"
)


def _strip_top_preamble_block(text: str) -> str:
    without_pre = TOP_PRE_BLOCK_PATTERN.sub("", text, count=1)
    if without_pre != text:
        return without_pre
    return TOP_FENCED_BLOCK_PATTERN.sub("", text, count=1)

def prepare_llm_dependency_text(raw_content: str) -> str:
    if not raw_content:
        return ""

    return _strip_top_preamble_block(raw_content).replace("\r\n", "\n").replace("\r", "\n").strip()


def _normalize_reference_number(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None

    if number < 0:
        return None

    if MAX_PROPOSAL_ID is not None and number > int(MAX_PROPOSAL_ID):
        return None

    return number


def _uses_hex_proposal_ids(proposal_label: str = PROPOSAL_LABEL, reference_pattern: str = REFERENCE_PATTERN) -> bool:
    return proposal_label.upper() == "NIP" or "A-F" in reference_pattern or "a-f" in reference_pattern


def _normalize_reference_id(
    value: Any,
    proposal_label: str = PROPOSAL_LABEL,
    reference_pattern: str = REFERENCE_PATTERN,
) -> str | None:
    text = str(value).strip()
    if not text:
        return None

    if _uses_hex_proposal_ids(proposal_label, reference_pattern):
        if not re.fullmatch(rf"[0-9A-Fa-f]{{1,{MAX_REFERENCE_DIGITS}}}", text):
            return None
        number = int(text, 16)
        if MAX_PROPOSAL_ID is not None and number > int(MAX_PROPOSAL_ID):
            return None
        normalized = text.upper()
        return normalized.zfill(2) if len(normalized) == 1 else normalized

    normalized_num = _normalize_reference_number(text)
    return None if normalized_num is None else str(normalized_num)


def _reference_sort_key(value: str, proposal_label: str = PROPOSAL_LABEL) -> tuple[int, str]:
    suffix = value.split()[-1]
    try:
        base = 16 if _uses_hex_proposal_ids(proposal_label) else 10
        return (int(suffix, base), suffix)
    except ValueError:
        return (10**12, suffix)


def create_reference_list(
    raw_content: str,
    proposal_label: str = PROPOSAL_LABEL,
    reference_pattern: str = REFERENCE_PATTERN,
) -> List[str]:
    normalized_reference_pattern = reference_pattern.replace(r"\d+", rf"\d{{1,{MAX_REFERENCE_DIGITS}}}")
    single_reference_pattern = re.compile(normalized_reference_pattern, re.IGNORECASE)
    proposal_references = {
        f"{proposal_label} {normalized_id}"
        for num in single_reference_pattern.findall(raw_content)
        for normalized_id in [_normalize_reference_id(num, proposal_label, reference_pattern)]
        if normalized_id is not None
    }

    if proposal_label == PROPOSAL_LABEL:
        list_pattern = HEX_REFERENCE_LIST_PATTERN if _uses_hex_proposal_ids(proposal_label, reference_pattern) else REFERENCE_LIST_PATTERN
        token_pattern = r"[0-9A-Fa-f]+" if _uses_hex_proposal_ids(proposal_label, reference_pattern) else r"\d+"
        for match in list_pattern.findall(raw_content):
            for raw_id in re.findall(token_pattern, match):
                normalized_id = _normalize_reference_id(raw_id, proposal_label, reference_pattern)
                if normalized_id is not None:
                    proposal_references.add(f"{proposal_label} {normalized_id}")

    return sorted(proposal_references, key=lambda value: _reference_sort_key(value, proposal_label))


def create_explicit_dependency_list(
    preamble: Dict[str, Any],
    proposal_label: str = PROPOSAL_LABEL,
) -> List[str]:
    label = re.escape(proposal_label)
    id_chars = r"[0-9A-Fa-f]" if _uses_hex_proposal_ids(proposal_label) else r"\d"
    id_pattern = re.compile(rf"(?i)(?:{label}[-\s]*)?({id_chars}+)")
    dependency_ids = set()
    preamble_interrelations = get_preamble_interrelations(preamble)

    for value in preamble_interrelations.values():
        if not value:
            continue

        raw_items = value if isinstance(value, list) else str(value).split(",")
        for item in raw_items:
            for proposal_id in id_pattern.findall(str(item)):
                normalized_id = _normalize_reference_id(proposal_id, proposal_label)
                if normalized_id is not None:
                    dependency_ids.add(f"{proposal_label} {normalized_id}")

    return sorted(dependency_ids, key=lambda value: _reference_sort_key(value, proposal_label))


def load_api_key() -> str | None:
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key

    secret_file = Path("apikey.secret")
    if secret_file.exists():
        with secret_file.open(encoding="utf-8") as f:
            return f.read().strip()

    return None


def normalize_dependency_output(
    payload: Any,
    proposal_label: str = PROPOSAL_LABEL,
    current_proposal_number: str | None = None,
) -> List[str]:
    if not isinstance(payload, list):
        return []

    label = re.escape(proposal_label)
    id_chars = r"[0-9A-Fa-f]" if _uses_hex_proposal_ids(proposal_label) else r"\d"
    id_pattern = re.compile(rf"(?i)^\s*(?:{label}[-\s]*)?({id_chars}+)\s*$")
    current_id = None if current_proposal_number is None else _normalize_reference_id(current_proposal_number, proposal_label)
    current_normalized = None if current_id is None else f"{proposal_label} {current_id}"
    normalized_ids = set()

    for item in payload:
        match = id_pattern.match(str(item))
        if not match:
            continue
        normalized_id = _normalize_reference_id(match.group(1), proposal_label)
        if normalized_id is None:
            continue
        normalized = f"{proposal_label} {normalized_id}"
        if normalized == current_normalized:
            continue
        normalized_ids.add(normalized)

    return sorted(normalized_ids, key=lambda value: _reference_sort_key(value, proposal_label))


def llm_extract_implicit_dependencies(
    text: str,
    current_proposal_number: str | None = None,
    proposal_label: str = PROPOSAL_LABEL,
    proposal_singular: str = PROPOSAL_SINGULAR,
    api_key: str | None = None,
    model: str = LLM_MODEL,
) -> List[str]:
    system_prompt = f"""
You extract implicit technical dependencies from {proposal_singular} documents.

Decision rule:
- Include another {proposal_label} only when the proposal materially builds on, requires, extends, constrains, amends, specializes, or otherwise substantively relies on concepts, mechanisms, formats, semantics, activation rules, or assumptions introduced by that {proposal_label}.
- Judge the technical context, not just surface mentions.
- If a candidate is ambiguous or weakly supported, omit it.

Do not include:
- mere mentions or citations
- history or background
- comparisons to alternative approaches
- examples
- topical relatedness
- speculation
- self-references

Output policy:
- Return JSON only, with no explanation and no markdown.
- Return a normalized, sorted, distinct list of {proposal_label}s in the form "{proposal_label} ID".
- Preserve hexadecimal identifiers and leading zeroes when the ecosystem uses them.
- Sort ascending by {proposal_label} identifier.
- Exclude {proposal_label} {current_proposal_number} if present.
- Return an empty list when there are no real dependencies.
""".strip()
    user_prompt = f"""
Analyze {proposal_singular} {proposal_label}{f" {current_proposal_number}" if current_proposal_number else ""}.

<examples>
<example>
<text>This proposal depends on {proposal_label} 39 and 32.</text>
<output>["{proposal_label} 32", "{proposal_label} 39"]</output>
</example>
<example>
<text>This proposal builds upon {proposal_label}-0016 for partially signed transactions.</text>
<output>["{proposal_label} 16"]</output>
</example>
<example>
<text>Since {proposal_label} 44 introduced a privacy concern, this proposal suggests a new hashing function to address that issue.</text>
<output>[]</output>
</example>
</examples>

Now apply the same rules to the actual proposal text below.

<proposal_text>
\"\"\"{text}\"\"\"
</proposal_text>
""".strip()
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": STRUCTURED_OUTPUT_NAME,
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "dependencies": {
                        "type": "array",
                        "items": {"type": "string"},
                    }
                },
                "required": ["dependencies"],
                "additionalProperties": False,
            },
        },
    }

    resolved_api_key = api_key or load_api_key()
    if not resolved_api_key:
        raise RuntimeError("No API key available for LLM extraction")

    client = OpenAI(api_key=resolved_api_key)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=response_format,
        )
        message = response.choices[0].message
        if getattr(message, "refusal", None):
            return []
        payload = json.loads(message.content.strip())
        return normalize_dependency_output(
            payload.get("dependencies"),
            proposal_label=proposal_label,
            current_proposal_number=current_proposal_number,
        )
    except TypeError:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        message = response.choices[0].message
        if getattr(message, "refusal", None):
            return []
        payload = json.loads(message.content.strip())
        return normalize_dependency_output(
            payload.get("dependencies"),
            proposal_label=proposal_label,
            current_proposal_number=current_proposal_number,
        )
    except (JSONDecodeError, TypeError, ValueError, KeyError, OSError, TimeoutError, ConnectionError) as exc:
        raise RuntimeError(f"LLM API call failed: {exc}") from exc
