import json
import os
import re
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, List, Mapping

from openai import OpenAI

from analysis.proposal_schema import get_preamble_interrelations
from pipeline.source_context import SourceContext


TOP_PRE_BLOCK_PATTERN = re.compile(r"^\s*<pre>.*?</pre>\s*", re.DOTALL | re.IGNORECASE)
TOP_FENCED_BLOCK_PATTERN = re.compile(r"^\s*```[^\n]*\n.*?\n```\s*(?:\n|$)", re.DOTALL)
STRUCTURED_OUTPUT_NAME = "implicit_dependency_list"
MAX_REFERENCE_DIGITS = 6


def _strip_top_preamble_block(text: str) -> str:
    without_pre = TOP_PRE_BLOCK_PATTERN.sub("", text, count=1)
    if without_pre != text:
        return without_pre
    return TOP_FENCED_BLOCK_PATTERN.sub("", text, count=1)

def prepare_llm_dependency_text(raw_content: str) -> str:
    if not raw_content:
        return ""

    return _strip_top_preamble_block(raw_content).replace("\r\n", "\n").replace("\r", "\n").strip()


def _normalize_reference_number(value: Any, max_proposal_id: Any = None) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None

    if number < 0:
        return None

    if max_proposal_id is not None and number > int(max_proposal_id):
        return None

    return number


def _uses_hex_proposal_ids(proposal_label: str = "IP", reference_pattern: str = "") -> bool:
    return proposal_label.upper() == "NIP" or "A-F" in reference_pattern or "a-f" in reference_pattern


def _reference_configs_for_context(
    context: SourceContext,
    proposal_label: str | None = None,
    reference_pattern: str | None = None,
) -> List[Dict[str, Any]]:
    configs: List[Dict[str, Any]] = []
    sources = context.ecosystem_source_configs

    for source_slug, source_config in sources.items():
        label = str(source_config.get("proposal_acronym") or "").strip()
        pattern = str(source_config.get("reference_pattern") or "").strip()
        if not label or not pattern:
            continue
        configs.append(
            {
                "source_slug": source_slug,
                "proposal_label": label,
                "reference_pattern": pattern,
                "max_proposal_id": source_config.get("max_proposal_id"),
            }
        )

    if not configs:
        configs.append(
            {
                "source_slug": context.source_slug,
                "proposal_label": proposal_label or context.proposal_label,
                "reference_pattern": reference_pattern or context.reference_pattern,
                "max_proposal_id": context.max_proposal_id,
            }
        )

    active_label = proposal_label or context.proposal_label
    active_pattern = reference_pattern or context.reference_pattern
    has_active = any(
        config["proposal_label"].upper() == active_label.upper()
        for config in configs
    )
    if not has_active and active_label and active_pattern:
        configs.insert(
            0,
            {
                "source_slug": context.source_slug,
                "proposal_label": active_label,
                "reference_pattern": active_pattern,
                "max_proposal_id": context.max_proposal_id,
            },
        )

    return configs


def _reference_label_order(configs: List[Dict[str, Any]]) -> Mapping[str, int]:
    return {
        str(config["proposal_label"]).upper(): index
        for index, config in enumerate(configs)
    }


def _normalize_reference_id(
    value: Any,
    proposal_label: str = "IP",
    reference_pattern: str = "",
    max_proposal_id: Any = None,
) -> str | None:
    text = str(value).strip()
    if not text:
        return None

    if _uses_hex_proposal_ids(proposal_label, reference_pattern):
        if not re.fullmatch(rf"[0-9A-Fa-f]{{1,{MAX_REFERENCE_DIGITS}}}", text):
            return None
        number = int(text, 16)
        if max_proposal_id is not None and number > int(max_proposal_id):
            return None
        normalized = text.upper()
        return normalized.zfill(2) if len(normalized) == 1 else normalized

    normalized_num = _normalize_reference_number(text, max_proposal_id=max_proposal_id)
    return None if normalized_num is None else str(normalized_num)


def _reference_sort_key(value: str, proposal_label: str = "IP", label_order: Mapping[str, int] | None = None) -> tuple[int, int, str]:
    parts = value.split()
    label = parts[0].upper() if parts else proposal_label.upper()
    suffix = value.split()[-1]
    try:
        base = 16 if _uses_hex_proposal_ids(proposal_label) else 10
        numeric = int(suffix, base)
    except ValueError:
        numeric = 10**12
    order = label_order.get(label, 0) if label_order else 0
    return (order, numeric, suffix)


def _format_reference(label: str, normalized_id: str) -> str:
    return f"{label} {normalized_id}"


def _id_chars_for_reference_config(config: Dict[str, Any]) -> str:
    return r"[0-9A-Fa-f]" if _uses_hex_proposal_ids(
        str(config["proposal_label"]),
        str(config["reference_pattern"]),
    ) else r"\d"


def _normalize_with_reference_config(value: Any, config: Dict[str, Any]) -> str | None:
    return _normalize_reference_id(
        value,
        str(config["proposal_label"]),
        str(config["reference_pattern"]),
        config.get("max_proposal_id"),
    )


def _match_reference_item(
    item: Any,
    config: Dict[str, Any],
    *,
    allow_bare: bool,
) -> str | None:
    text = str(item).strip()
    if not text:
        return None

    label = re.escape(str(config["proposal_label"]))
    id_chars = _id_chars_for_reference_config(config)
    if allow_bare:
        pattern = re.compile(rf"(?i)^\s*(?:{label}[-#\s]*)?({id_chars}+)\s*$")
    else:
        pattern = re.compile(rf"(?i)^\s*{label}[-#\s]*({id_chars}+)\s*$")
    match = pattern.match(text)
    if not match:
        return None
    normalized_id = _normalize_with_reference_config(match.group(1), config)
    return None if normalized_id is None else _format_reference(str(config["proposal_label"]), normalized_id)


def create_reference_list(
    raw_content: str,
    proposal_label: str | None = None,
    reference_pattern: str | None = None,
    source_context: SourceContext | None = None,
) -> List[str]:
    context = source_context or SourceContext.default()
    reference_configs = _reference_configs_for_context(context, proposal_label, reference_pattern)
    label_order = _reference_label_order(reference_configs)
    proposal_references = set()

    for config in reference_configs:
        active_proposal_label = str(config["proposal_label"])
        active_reference_pattern = str(config["reference_pattern"])
        normalized_reference_pattern = active_reference_pattern.replace(r"\d+", rf"\d{{1,{MAX_REFERENCE_DIGITS}}}")
        single_reference_pattern = re.compile(normalized_reference_pattern, re.IGNORECASE)

        for num in single_reference_pattern.findall(raw_content):
            normalized_id = _normalize_with_reference_config(num, config)
            if normalized_id is not None:
                proposal_references.add(_format_reference(active_proposal_label, normalized_id))

        if _uses_hex_proposal_ids(active_proposal_label, active_reference_pattern):
            list_pattern = re.compile(
                rf"(?i)\b{re.escape(active_proposal_label)}s?[-#\s]*([0-9A-Fa-f]{{1,{MAX_REFERENCE_DIGITS}}}(?![0-9A-Fa-f])(?:\s*(?:,|/|and|or)\s*[0-9A-Fa-f]{{1,{MAX_REFERENCE_DIGITS}}}(?![0-9A-Fa-f]))*)"
            )
            token_pattern = r"[0-9A-Fa-f]+"
        else:
            list_pattern = re.compile(
                rf"(?i)\b{re.escape(active_proposal_label)}s?[-#\s]*(\d{{1,{MAX_REFERENCE_DIGITS}}}(?!\d)(?:\s*(?:,|/|and|or)\s*\d{{1,{MAX_REFERENCE_DIGITS}}}(?!\d))*)"
            )
            token_pattern = r"\d+"

        for match in list_pattern.findall(raw_content):
            for raw_id in re.findall(token_pattern, match):
                normalized_id = _normalize_with_reference_config(raw_id, config)
                if normalized_id is not None:
                    proposal_references.add(_format_reference(active_proposal_label, normalized_id))

    active_label = proposal_label or context.proposal_label
    return sorted(proposal_references, key=lambda value: _reference_sort_key(value, active_label, label_order))


def create_explicit_dependency_list(
    preamble: Dict[str, Any],
    proposal_label: str | None = None,
    source_context: SourceContext | None = None,
) -> List[str]:
    context = source_context or SourceContext.default()
    reference_configs = _reference_configs_for_context(context, proposal_label, context.reference_pattern)
    active_label = proposal_label or context.proposal_label
    active_config = next(
        (
            config
            for config in reference_configs
            if str(config["proposal_label"]).upper() == active_label.upper()
        ),
        reference_configs[0],
    )
    label_order = _reference_label_order(reference_configs)
    dependency_ids = set()
    preamble_interrelations = get_preamble_interrelations(preamble, source_context=context)

    for value in preamble_interrelations.values():
        if not value:
            continue

        raw_items = value if isinstance(value, list) else str(value).split(",")
        for item in raw_items:
            matched = False
            for config in reference_configs:
                normalized = _match_reference_item(item, config, allow_bare=False)
                if normalized is not None:
                    dependency_ids.add(normalized)
                    matched = True
            if matched:
                continue
            normalized = _match_reference_item(item, active_config, allow_bare=True)
            if normalized is not None:
                dependency_ids.add(normalized)

    return sorted(dependency_ids, key=lambda value: _reference_sort_key(value, active_label, label_order))


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
    proposal_label: str | None = None,
    current_proposal_number: str | None = None,
    source_context: SourceContext | None = None,
) -> List[str]:
    if not isinstance(payload, list):
        return []

    context = source_context or SourceContext.default()
    reference_configs = _reference_configs_for_context(context, proposal_label, context.reference_pattern)
    active_proposal_label = proposal_label or context.proposal_label
    active_config = next(
        (
            config
            for config in reference_configs
            if str(config["proposal_label"]).upper() == active_proposal_label.upper()
        ),
        reference_configs[0],
    )
    label_order = _reference_label_order(reference_configs)
    current_id = None if current_proposal_number is None else _normalize_reference_id(
        current_proposal_number,
        active_proposal_label,
        str(active_config["reference_pattern"]),
        active_config.get("max_proposal_id"),
    )
    current_normalized = None if current_id is None else f"{active_proposal_label} {current_id}"
    normalized_ids = set()

    for item in payload:
        normalized = None
        for config in reference_configs:
            normalized = _match_reference_item(item, config, allow_bare=False)
            if normalized is not None:
                break
        if normalized is None:
            normalized = _match_reference_item(item, active_config, allow_bare=True)
        if normalized is None:
            continue
        if normalized == current_normalized:
            continue
        normalized_ids.add(normalized)

    return sorted(normalized_ids, key=lambda value: _reference_sort_key(value, active_proposal_label, label_order))


def llm_extract_implicit_dependencies(
    text: str,
    current_proposal_number: str | None = None,
    proposal_label: str | None = None,
    proposal_singular: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    source_context: SourceContext | None = None,
) -> List[str]:
    context = source_context or SourceContext.default()
    resolved_model = model or context.llm_model
    if not resolved_model:
        raise RuntimeError("No LLM model configured. Set `llm.model` in the ecosystem YAML.")
    active_proposal_label = proposal_label or context.proposal_label
    active_proposal_singular = proposal_singular or context.proposal_singular
    reference_configs = _reference_configs_for_context(context, active_proposal_label, context.reference_pattern)
    source_labels = ", ".join(
        f"{config['proposal_label']} ({config['source_slug']})"
        for config in reference_configs
    )
    system_prompt = f"""
You extract implicit technical dependencies from {active_proposal_singular} documents.

Decision rule:
- Include another proposal only when the proposal materially builds on, requires, extends, constrains, amends, specializes, or otherwise substantively relies on concepts, mechanisms, formats, semantics, activation rules, or assumptions introduced by that proposal.
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
- Return a normalized, sorted, distinct list using source labels in the form "LABEL ID".
- Valid labels for this ecosystem: {source_labels}.
- Preserve hexadecimal identifiers and leading zeroes when the ecosystem uses them.
- Sort by source label, then ascending proposal identifier.
- Exclude {active_proposal_label} {current_proposal_number} if present.
- Return an empty list when there are no real dependencies.
""".strip()
    user_prompt = f"""
Analyze {active_proposal_singular} {active_proposal_label}{f" {current_proposal_number}" if current_proposal_number else ""}.

<examples>
<example>
<text>This proposal depends on {active_proposal_label} 39 and 32.</text>
<output>["{active_proposal_label} 32", "{active_proposal_label} 39"]</output>
</example>
<example>
<text>This proposal builds upon {active_proposal_label}-0016 for partially signed transactions.</text>
<output>["{active_proposal_label} 16"]</output>
</example>
<example>
<text>Since {active_proposal_label} 44 introduced a privacy concern, this proposal suggests a new hashing function to address that issue.</text>
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
            model=resolved_model,
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
            proposal_label=active_proposal_label,
            current_proposal_number=current_proposal_number,
            source_context=context,
        )
    except TypeError:
        response = client.chat.completions.create(
            model=resolved_model,
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
            proposal_label=active_proposal_label,
            current_proposal_number=current_proposal_number,
            source_context=context,
        )
    except (JSONDecodeError, TypeError, ValueError, KeyError, OSError, TimeoutError, ConnectionError) as exc:
        raise RuntimeError(f"LLM API call failed: {exc}") from exc
