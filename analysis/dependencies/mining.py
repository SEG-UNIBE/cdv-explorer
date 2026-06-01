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


def create_reference_list(
    raw_content: str,
    proposal_label: str = PROPOSAL_LABEL,
    reference_pattern: str = REFERENCE_PATTERN,
) -> List[str]:
    normalized_reference_pattern = reference_pattern.replace(r"\d+", rf"\d{{1,{MAX_REFERENCE_DIGITS}}}")
    single_reference_pattern = re.compile(normalized_reference_pattern, re.IGNORECASE)
    proposal_references = {
        f"{proposal_label} {normalized_num}"
        for num in single_reference_pattern.findall(raw_content)
        for normalized_num in [_normalize_reference_number(num)]
        if normalized_num is not None
    }

    if proposal_label == PROPOSAL_LABEL:
        for match in REFERENCE_LIST_PATTERN.findall(raw_content):
            for num in re.findall(r"\d+", match):
                normalized_num = _normalize_reference_number(num)
                if normalized_num is not None:
                    proposal_references.add(f"{proposal_label} {normalized_num}")

    return sorted(proposal_references, key=lambda value: int(value.split()[-1]))


def create_explicit_dependency_list(
    preamble: Dict[str, Any],
    proposal_label: str = PROPOSAL_LABEL,
) -> List[str]:
    label = re.escape(proposal_label)
    id_pattern = re.compile(rf"(?i)(?:{label}[-\s]*)?(\d+)")
    dependency_ids = set()
    preamble_interrelations = get_preamble_interrelations(preamble)

    for value in preamble_interrelations.values():
        if not value:
            continue

        raw_items = value if isinstance(value, list) else str(value).split(",")
        for item in raw_items:
            for proposal_id in id_pattern.findall(str(item)):
                normalized_num = _normalize_reference_number(proposal_id)
                if normalized_num is not None:
                    dependency_ids.add(f"{proposal_label} {normalized_num}")

    return sorted(dependency_ids)


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
    id_pattern = re.compile(rf"(?i)^\s*(?:{label}[-\s]*)?0*(\d+)\s*$")
    current_normalized = None if current_proposal_number is None else f"{proposal_label} {int(current_proposal_number)}"
    normalized_ids = set()

    for item in payload:
        match = id_pattern.match(str(item))
        if not match:
            continue
        normalized_num = _normalize_reference_number(match.group(1))
        if normalized_num is None:
            continue
        normalized = f"{proposal_label} {normalized_num}"
        if normalized == current_normalized:
            continue
        normalized_ids.add(normalized)

    return sorted(normalized_ids, key=lambda value: int(value.split()[-1]))


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
- Return a normalized, sorted, distinct list of {proposal_label}s in the form "{proposal_label} N".
- Sort ascending by numeric {proposal_label} identifier.
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
