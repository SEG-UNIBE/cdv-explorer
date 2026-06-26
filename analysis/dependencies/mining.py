import os
import re
from json import JSONDecodeError, loads
from pathlib import Path
from typing import Any, Dict, List, Mapping

from openai import OpenAI

from analysis.reference_ids import (
    normalize_reference_id,
    normalize_reference_id_for_config,
    uses_hex_proposal_ids,
)
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

    return (
        _strip_top_preamble_block(raw_content)
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .strip()
    )


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
        config["proposal_label"].upper() == active_label.upper() for config in configs
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


def _reference_patterns_by_label(configs: List[Dict[str, Any]]) -> Mapping[str, str]:
    return {
        str(config["proposal_label"]).upper(): str(config["reference_pattern"])
        for config in configs
    }


def _normalize_reference_id(
    value: Any,
    proposal_label: str = "IP",
    reference_pattern: str = "",
    max_proposal_id: Any = None,
) -> str | None:
    return normalize_reference_id(
        value,
        proposal_label=proposal_label,
        reference_pattern=reference_pattern,
        max_proposal_id=max_proposal_id,
        max_reference_digits=MAX_REFERENCE_DIGITS,
    )


def _reference_sort_key(
    value: str,
    proposal_label: str = "IP",
    label_order: Mapping[str, int] | None = None,
    reference_patterns_by_label: Mapping[str, str] | None = None,
) -> tuple[int, int, str]:
    parts = value.split()
    label = parts[0].upper() if parts else proposal_label.upper()
    suffix = parts[-1] if parts else ""
    reference_pattern = (reference_patterns_by_label or {}).get(label, "")
    try:
        base = 16 if uses_hex_proposal_ids(label, reference_pattern) else 10
        numeric = int(suffix, base)
    except ValueError:
        numeric = 10**12
    order = label_order.get(label, 0) if label_order else 0
    return (order, numeric, suffix)


def _format_reference(label: str, normalized_id: str) -> str:
    return f"{label} {normalized_id}"


def _id_chars_for_reference_config(config: Dict[str, Any]) -> str:
    return (
        r"[0-9A-Fa-f]"
        if uses_hex_proposal_ids(
            str(config["proposal_label"]),
            str(config["reference_pattern"]),
        )
        else r"\d"
    )


def _normalize_with_reference_config(value: Any, config: Dict[str, Any]) -> str | None:
    return normalize_reference_id_for_config(
        value,
        config,
        max_reference_digits=MAX_REFERENCE_DIGITS,
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
    return (
        None
        if normalized_id is None
        else _format_reference(str(config["proposal_label"]), normalized_id)
    )


def create_reference_list(
    raw_content: str,
    proposal_label: str | None = None,
    reference_pattern: str | None = None,
    source_context: SourceContext | None = None,
) -> List[str]:
    context = source_context or SourceContext.default()
    reference_configs = _reference_configs_for_context(
        context, proposal_label, reference_pattern
    )
    label_order = _reference_label_order(reference_configs)
    reference_patterns_by_label = _reference_patterns_by_label(reference_configs)
    proposal_references = set()

    for config in reference_configs:
        active_proposal_label = str(config["proposal_label"])
        active_reference_pattern = str(config["reference_pattern"])
        normalized_reference_pattern = active_reference_pattern.replace(
            r"\d+", rf"\d{{1,{MAX_REFERENCE_DIGITS}}}"
        )
        single_reference_pattern = re.compile(
            normalized_reference_pattern, re.IGNORECASE
        )

        for num in single_reference_pattern.findall(raw_content):
            normalized_id = _normalize_with_reference_config(num, config)
            if normalized_id is not None:
                proposal_references.add(
                    _format_reference(active_proposal_label, normalized_id)
                )

        if uses_hex_proposal_ids(active_proposal_label, active_reference_pattern):
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
                    proposal_references.add(
                        _format_reference(active_proposal_label, normalized_id)
                    )

    active_label = proposal_label or context.proposal_label
    return sorted(
        proposal_references,
        key=lambda value: _reference_sort_key(
            value, active_label, label_order, reference_patterns_by_label
        ),
    )


def _format_target_key(source_slug: Any, proposal_id: Any) -> str:
    return f"{source_slug}:{proposal_id}"


def _resolve_target_reference(
    item: Any,
    reference_configs: List[Dict[str, Any]],
    active_config: Dict[str, Any],
) -> Dict[str, str] | None:
    if isinstance(item, dict):
        target = item.get("target")
        if isinstance(target, str) and ":" in target:
            source_slug, proposal_id = target.split(":", 1)
            matching_config = next(
                (
                    config
                    for config in reference_configs
                    if str(config["source_slug"]) == source_slug
                ),
                active_config,
            )
            normalized_id = _normalize_with_reference_config(
                proposal_id, matching_config
            )
            if normalized_id is None:
                return None
            return {
                "source_slug": str(matching_config["source_slug"]),
                "proposal_id": normalized_id,
                "label": _format_reference(
                    str(matching_config["proposal_label"]), normalized_id
                ),
            }

    for config in reference_configs:
        normalized = _match_reference_item(item, config, allow_bare=False)
        if normalized is None:
            continue
        return {
            "source_slug": str(config["source_slug"]),
            "proposal_id": normalized.split(" ", 1)[1],
            "label": normalized,
        }

    normalized = _match_reference_item(item, active_config, allow_bare=True)
    if normalized is None:
        return None
    return {
        "source_slug": str(active_config["source_slug"]),
        "proposal_id": normalized.split(" ", 1)[1],
        "label": normalized,
    }


def create_reference_targets(
    raw_content: str,
    proposal_label: str | None = None,
    reference_pattern: str | None = None,
    source_context: SourceContext | None = None,
) -> List[Dict[str, Any]]:
    context = source_context or SourceContext.default()
    reference_configs = _reference_configs_for_context(
        context, proposal_label, reference_pattern
    )
    active_label = proposal_label or context.proposal_label
    label_order = _reference_label_order(reference_configs)
    reference_patterns_by_label = _reference_patterns_by_label(reference_configs)
    counts: Dict[str, Dict[str, Any]] = {}

    for config in reference_configs:
        active_proposal_label = str(config["proposal_label"])
        active_reference_pattern = str(config["reference_pattern"])

        if uses_hex_proposal_ids(active_proposal_label, active_reference_pattern):
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
                if normalized_id is None:
                    continue
                target = _format_target_key(config["source_slug"], normalized_id)
                counts.setdefault(
                    target,
                    {
                        "target": target,
                        "count": 0,
                        "_label": _format_reference(
                            active_proposal_label, normalized_id
                        ),
                    },
                )["count"] += 1

    items = sorted(
        counts.values(),
        key=lambda item: _reference_sort_key(
            item["_label"], active_label, label_order, reference_patterns_by_label
        ),
    )
    return [{"target": item["target"], "count": item["count"]} for item in items]


def create_explicit_dependency_list(
    preamble: Dict[str, Any],
    proposal_label: str | None = None,
    source_context: SourceContext | None = None,
) -> List[str]:
    context = source_context or SourceContext.default()
    reference_configs = _reference_configs_for_context(
        context, proposal_label, context.reference_pattern
    )
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
    reference_patterns_by_label = _reference_patterns_by_label(reference_configs)
    dependency_ids = set()
    preamble_interrelations = get_preamble_interrelations(
        preamble, source_context=context
    )

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

    return sorted(
        dependency_ids,
        key=lambda value: _reference_sort_key(
            value, active_label, label_order, reference_patterns_by_label
        ),
    )


def create_explicit_dependency_targets(
    preamble: Dict[str, Any],
    proposal_label: str | None = None,
    source_context: SourceContext | None = None,
) -> List[Dict[str, str]]:
    context = source_context or SourceContext.default()
    reference_configs = _reference_configs_for_context(
        context, proposal_label, context.reference_pattern
    )
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
    reference_patterns_by_label = _reference_patterns_by_label(reference_configs)
    preamble_interrelations = get_preamble_interrelations(
        preamble, source_context=context
    )
    result: List[Dict[str, str]] = []

    for subtype in context.preamble_interrelation_types:
        value = preamble_interrelations.get(subtype)
        if not value:
            continue
        raw_items = value if isinstance(value, list) else str(value).split(",")
        targets: Dict[str, Dict[str, str]] = {}
        for item in raw_items:
            reference = _resolve_target_reference(
                item, reference_configs, active_config
            )
            if reference is None:
                continue
            target = _format_target_key(
                reference["source_slug"], reference["proposal_id"]
            )
            targets[target] = {"target": target, "_label": reference["label"]}
        ordered = sorted(
            targets.values(),
            key=lambda item: _reference_sort_key(
                item["_label"], active_label, label_order, reference_patterns_by_label
            ),
        )
        result.extend({"target": item["target"], "type": subtype} for item in ordered)

    return result


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
    reference_configs = _reference_configs_for_context(
        context, proposal_label, context.reference_pattern
    )
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
    reference_patterns_by_label = _reference_patterns_by_label(reference_configs)
    current_id = (
        None
        if current_proposal_number is None
        else _normalize_reference_id(
            current_proposal_number,
            active_proposal_label,
            str(active_config["reference_pattern"]),
            active_config.get("max_proposal_id"),
        )
    )
    current_normalized = (
        None if current_id is None else f"{active_proposal_label} {current_id}"
    )
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

    return sorted(
        normalized_ids,
        key=lambda value: _reference_sort_key(
            value, active_proposal_label, label_order, reference_patterns_by_label
        ),
    )


def _resolve_llm_target(
    item: Any,
    reference_configs: List[Dict[str, Any]],
    active_config: Dict[str, Any],
) -> Dict[str, str] | None:
    raw_target = item
    raw_source = None
    raw_id = None

    if isinstance(item, dict):
        raw_source = item.get("target_source") or item.get("source_slug")
        raw_id = item.get("target_id") or item.get("proposal_id") or item.get("id")
        raw_target = item.get("target") or item.get("label") or item.get("dependency")

    if raw_source and raw_id is not None:
        matching_config = next(
            (
                config
                for config in reference_configs
                if str(config.get("source_slug")) == str(raw_source)
            ),
            active_config,
        )
        normalized_id = _normalize_with_reference_config(raw_id, matching_config)
        if normalized_id is None:
            return None
        return {
            "source_slug": str(matching_config["source_slug"]),
            "proposal_id": normalized_id,
            "label": _format_reference(
                str(matching_config["proposal_label"]), normalized_id
            ),
        }

    if raw_target is None:
        return None

    target_text = str(raw_target).strip()
    if not target_text:
        return None

    if ":" in target_text:
        target_source, target_id = target_text.split(":", 1)
        matching_config = next(
            (
                config
                for config in reference_configs
                if str(config.get("source_slug")) == target_source
            ),
            active_config,
        )
        normalized_id = _normalize_with_reference_config(target_id, matching_config)
        if normalized_id is None:
            return None
        return {
            "source_slug": str(matching_config["source_slug"]),
            "proposal_id": normalized_id,
            "label": _format_reference(
                str(matching_config["proposal_label"]), normalized_id
            ),
        }

    for config in reference_configs:
        normalized = _match_reference_item(target_text, config, allow_bare=False)
        if normalized is None:
            continue
        return {
            "source_slug": str(config["source_slug"]),
            "proposal_id": normalized.split(" ", 1)[1],
            "label": normalized,
        }

    normalized = _match_reference_item(target_text, active_config, allow_bare=True)
    if normalized is None:
        return None
    return {
        "source_slug": str(active_config["source_slug"]),
        "proposal_id": normalized.split(" ", 1)[1],
        "label": normalized,
    }


def normalize_llm_dependency_output(
    payload: Any,
    proposal_label: str | None = None,
    current_proposal_number: str | None = None,
    source_context: SourceContext | None = None,
) -> List[Dict[str, str]]:
    if not isinstance(payload, list):
        return []

    context = source_context or SourceContext.default()
    reference_configs = _reference_configs_for_context(
        context, proposal_label, context.reference_pattern
    )
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
    reference_patterns_by_label = _reference_patterns_by_label(reference_configs)
    current_id = (
        None
        if current_proposal_number is None
        else _normalize_with_reference_config(
            current_proposal_number,
            active_config,
        )
    )
    current_target = (
        None if current_id is None else f"{active_config['source_slug']}:{current_id}"
    )
    normalized_entries: List[Dict[str, str]] = []
    seen_targets = set()

    for item in payload:
        target = _resolve_llm_target(item, reference_configs, active_config)
        if target is None:
            continue
        target_key = f"{target['source_slug']}:{target['proposal_id']}"
        if target_key == current_target or target_key in seen_targets:
            continue
        seen_targets.add(target_key)

        evidence = (
            str(item.get("evidence", "")).strip() if isinstance(item, dict) else ""
        )
        reason = str(item.get("reason", "")).strip() if isinstance(item, dict) else ""
        confidence = (
            str(item.get("confidence", "low")).strip().lower()
            if isinstance(item, dict)
            else "low"
        )
        if confidence not in {"low", "medium", "high"}:
            confidence = "low"

        normalized_entries.append(
            {
                "target": target_key,
                "evidence": evidence,
                "reason": reason,
                "confidence": confidence,
                "_label": target["label"],
            }
        )

    sorted_entries = sorted(
        normalized_entries,
        key=lambda entry: _reference_sort_key(
            entry.get("_label", ""),
            active_proposal_label,
            label_order,
            reference_patterns_by_label,
        ),
    )
    return [
        {key: value for key, value in entry.items() if not key.startswith("_")}
        for entry in sorted_entries
    ]


def _ground_evidence(
    entries: List[Dict[str, str]], source_text: str
) -> List[Dict[str, str]]:
    """Lower confidence to 'low' when the LLM's evidence quote cannot be found verbatim in the source."""
    if not source_text:
        return entries
    normalized_text = re.sub(r"\s+", " ", source_text).lower()
    result = []
    for entry in entries:
        evidence = entry.get("evidence", "")
        if evidence:
            normalized_evidence = re.sub(r"\s+", " ", evidence).strip().lower()
            if normalized_evidence and normalized_evidence not in normalized_text:
                entry = {**entry, "confidence": "low"}
        result.append(entry)
    return result


def _extract_response_content(response: Any) -> str | None:
    """Extract JSON text from either a Chat Completions or Responses API response."""
    # Chat Completions API: response.choices[*].message
    choices = getattr(response, "choices", None)
    if choices:
        message = choices[0].message
        if getattr(message, "refusal", None):
            return None
        return (message.content or "").strip() or None
    # Responses API: failed status
    if getattr(response, "status", None) == "failed":
        return None
    # Responses API: output_text convenience property
    output_text = getattr(response, "output_text", None)
    if output_text is not None:
        return output_text.strip() or None
    # Responses API: iterate output items
    for item in getattr(response, "output", []):
        for content in getattr(item, "content", []):
            text = getattr(content, "text", None)
            if text:
                return text.strip()
    return None


def _to_responses_text_format(response_format: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a Chat Completions response_format dict to Responses API text.format shape."""
    if (
        response_format.get("type") == "json_schema"
        and "json_schema" in response_format
    ):
        return {"type": "json_schema", **response_format["json_schema"]}
    return dict(response_format)


def _dependencies_from_llm_response(
    response: Any,
    *,
    proposal_label: str,
    current_proposal_number: str | None,
    source_context: SourceContext,
) -> List[Dict[str, str]]:
    content = _extract_response_content(response)
    if content is None:
        return []
    payload = loads(content)
    return normalize_llm_dependency_output(
        payload.get("dependencies"),
        proposal_label=proposal_label,
        current_proposal_number=current_proposal_number,
        source_context=source_context,
    )


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
        raise RuntimeError(
            "No LLM model configured. Set `llm.model` in the ecosystem YAML."
        )
    active_proposal_label = proposal_label or context.proposal_label
    active_proposal_singular = proposal_singular or context.proposal_singular
    reference_configs = _reference_configs_for_context(
        context, active_proposal_label, context.reference_pattern
    )
    active_config = next(
        (
            config
            for config in reference_configs
            if str(config["proposal_label"]).upper() == active_proposal_label.upper()
        ),
        reference_configs[0],
    )
    source_labels = ", ".join(
        f"{config['proposal_label']} ({config['source_slug']})"
        for config in reference_configs
    )
    target_formats = ", ".join(
        f"{config['proposal_label']} => {config['source_slug']}:ID"
        for config in reference_configs
    )
    sibling_config = next(
        (
            c
            for c in reference_configs
            if c["source_slug"] != active_config["source_slug"]
        ),
        None,
    )
    if sibling_config:
        cross_source_example = f"""
<example>
<text>This proposal uses the version byte registry from {sibling_config["proposal_label"]} 132 and builds on {active_proposal_label} 32 for key derivation.</text>
<output>{{"dependencies":[{{"target":"{active_config["source_slug"]}:32","evidence":"builds on {active_proposal_label} 32 for key derivation","reason":"The proposal extends key derivation mechanisms from the target.","confidence":"high"}},{{"target":"{sibling_config["source_slug"]}:132","evidence":"uses the version byte registry from {sibling_config["proposal_label"]} 132","reason":"The proposal relies on version byte definitions established by the target.","confidence":"high"}}]}}</output>
</example>
"""
    else:
        cross_source_example = ""
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
- Return a normalized, sorted, distinct list of dependency objects.
- Each object must use target format "source_slug:ID".
- Valid labels for this ecosystem: {source_labels}.
- Target format mapping: {target_formats}.
- Preserve hexadecimal identifiers and leading zeroes when the ecosystem uses them.
- Sort by source label, then ascending proposal identifier.
- Exclude {active_proposal_label} {current_proposal_number} if present.
- Return an empty list when there are no real dependencies.
- Evidence must be a short exact quote or close excerpt from the proposal text.
- Reason must briefly explain why the target is a technical dependency, not just a citation.
- Confidence must be one of: low, medium, high.
""".strip()
    user_prompt = f"""
Analyze {active_proposal_singular} {active_proposal_label}{f" {current_proposal_number}" if current_proposal_number else ""}.

<examples>
<example>
<text>This proposal depends on {active_proposal_label} 39 and 32.</text>
<output>{{"dependencies":[{{"target":"{active_config["source_slug"]}:32","evidence":"depends on {active_proposal_label} 39 and 32","reason":"The proposal explicitly says it depends on this target.","confidence":"high"}},{{"target":"{active_config["source_slug"]}:39","evidence":"depends on {active_proposal_label} 39 and 32","reason":"The proposal explicitly says it depends on this target.","confidence":"high"}}]}}</output>
</example>
<example>
<text>This proposal builds upon {active_proposal_label}-0016 for partially signed transactions.</text>
<output>{{"dependencies":[{{"target":"{active_config["source_slug"]}:16","evidence":"builds upon {active_proposal_label}-0016 for partially signed transactions","reason":"The proposal builds on mechanisms introduced by the target.","confidence":"high"}}]}}</output>
</example>
<example>
<text>Unlike {active_proposal_label} 44, which defines a symmetric encryption scheme, this proposal introduces a standalone asymmetric key agreement protocol. No primitives or formats from {active_proposal_label} 44 are reused.</text>
<output>{{"dependencies":[]}}</output>
</example>
{cross_source_example}</examples>

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
                        "items": {
                            "type": "object",
                            "properties": {
                                "target": {"type": "string"},
                                "evidence": {"type": "string"},
                                "reason": {"type": "string"},
                                "confidence": {
                                    "type": "string",
                                    "enum": ["low", "medium", "high"],
                                },
                            },
                            "required": ["target", "evidence", "reason", "confidence"],
                            "additionalProperties": False,
                        },
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

    llm_reasoning = context.llm_reasoning

    client = OpenAI(api_key=resolved_api_key)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    def _parse(response: Any) -> List[Dict[str, str]]:
        results = _dependencies_from_llm_response(
            response,
            proposal_label=active_proposal_label,
            current_proposal_number=current_proposal_number,
            source_context=context,
        )
        return _ground_evidence(results, text)

    if llm_reasoning is not None:
        # Responses API path (reasoning models)
        try:
            kwargs: Dict[str, Any] = {
                "model": resolved_model,
                "input": messages,
                "text": {"format": _to_responses_text_format(response_format)},
            }
            if llm_reasoning:
                kwargs["reasoning"] = llm_reasoning
            response = client.responses.create(**kwargs)
            return _parse(response)
        except (
            JSONDecodeError,
            TypeError,
            ValueError,
            KeyError,
            OSError,
            TimeoutError,
            ConnectionError,
        ) as exc:
            raise RuntimeError(f"LLM API call failed: {exc}") from exc
    else:
        # Chat Completions API path
        try:
            try:
                response = client.chat.completions.create(
                    model=resolved_model,
                    messages=messages,
                    response_format=response_format,
                )
            except TypeError:
                response = client.chat.completions.create(
                    model=resolved_model,
                    messages=messages,
                    response_format={"type": "json_object"},
                )
            return _parse(response)
        except (
            JSONDecodeError,
            TypeError,
            ValueError,
            KeyError,
            OSError,
            TimeoutError,
            ConnectionError,
        ) as exc:
            raise RuntimeError(f"LLM API call failed: {exc}") from exc
