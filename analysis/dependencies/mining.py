import json
import os
import re
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, List

from openai import OpenAI

from ecosystem_config import ACTIVE_ECOSYSTEM


PROPOSAL_LABEL = ACTIVE_ECOSYSTEM["proposal_acronym"]
PROPOSAL_SINGULAR = ACTIVE_ECOSYSTEM["proposal_term_singular"]
REFERENCE_PATTERN = ACTIVE_ECOSYSTEM["reference_pattern"]
LLM_MODEL = "gpt-5-nano"


def create_reference_list(
    raw_content: str,
    proposal_label: str = PROPOSAL_LABEL,
    reference_pattern: str = REFERENCE_PATTERN,
) -> List[str]:
    proposal_references = re.findall(reference_pattern, raw_content)
    return sorted(set(f"{proposal_label} {int(num)}" for num in proposal_references))


def create_explicit_dependency_list(
    preamble: Dict[str, Any],
    proposal_label: str = PROPOSAL_LABEL,
) -> List[str]:
    dependency_fields = ["requires", "replaces", "superseded_by"]
    label = re.escape(proposal_label)
    id_pattern = re.compile(rf"(?i)(?:{label}[-\s]*)?(\d+)")
    dependency_ids = set()

    for field in dependency_fields:
        value = preamble.get(field)
        if not value:
            continue

        raw_items = value if isinstance(value, list) else str(value).split(",")
        for item in raw_items:
            for proposal_id in id_pattern.findall(str(item)):
                dependency_ids.add(f"{proposal_label} {int(proposal_id)}")

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


def llm_extract_implicit_dependencies(
    text: str,
    current_proposal_number: str | None = None,
    proposal_label: str = PROPOSAL_LABEL,
    proposal_singular: str = PROPOSAL_SINGULAR,
    api_key: str | None = None,
    model: str = LLM_MODEL,
) -> List[str]:
    prompt = f"""
Analyze {proposal_singular} {proposal_label}{f" {current_proposal_number}" if current_proposal_number else ""}.

Task:
Return only the other {proposal_label}s that this proposal materially depends on.

Dependencies may be explicit or implicit.
Count another {proposal_label} as a dependency when the proposal materially builds on, requires, extends, constrains, amends, specializes, or otherwise substantively relies on concepts, mechanisms, formats, semantics, activation rules, or assumptions introduced by that {proposal_label}, even if the text does not say "depends on" directly.

Do not include:
- mere mentions or citations
- history or background
- comparisons to alternative approaches
- examples
- topical relatedness
- speculation
- self-references

Judge the technical context, not just surface mentions.
Be conservative. If the text does not provide strong evidence that another {proposal_label} is a real dependency, do not include it.

Output requirements:
- Return only a JSON array
- No explanation
- No markdown
- Deduplicate results
- Normalize identifiers to "{proposal_label} N" (for example "{proposal_label}-0016" -> "{proposal_label} 16")
- Exclude {proposal_label} {current_proposal_number} if present
- Return [] if there are no real dependencies

Examples:
Text: This proposal depends on {proposal_label} 32 and {proposal_label} 39.
Output: ["{proposal_label} 32", "{proposal_label} 39"]

Text: This proposal builds upon {proposal_label}-0016 for partially signed transactions.
Output: ["{proposal_label} 16"]

Text: Since {proposal_label} 44 introduced a privacy concern, this proposal suggests a new hashing function to address that issue.
Output: []

Text:
\"\"\"{text}\"\"\"
"""

    resolved_api_key = api_key or load_api_key()
    if not resolved_api_key:
        return []

    client = OpenAI(api_key=resolved_api_key)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        payload = json.loads(response.choices[0].message.content.strip())
        return payload if isinstance(payload, list) else []
    except (JSONDecodeError, TypeError, ValueError, KeyError, OSError, TimeoutError, ConnectionError):
        return []

