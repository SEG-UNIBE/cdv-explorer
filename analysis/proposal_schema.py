from typing import Any, Dict, List

from pipeline.source_context import SourceContext


META_KEYS = ("last_commit", "total_commits", "git_history")
OBSOLETE_INTERRELATION_KEYS = {
    "explicit_dependencies",
    "explicit_references",
    "implicit_dependencies",
}
LEGACY_TOP_LEVEL_KEYS = {"metadata", "history", "compliance"}
LLM_RUN_STATUS_SUCCESS = "success"
LLM_RUN_STATUS_REFUSAL = "refusal"
LLM_RUN_STATUS_PARSE_ERROR = "parse_error"
LLM_RUN_STATUS_API_ERROR = "api_error"
LLM_RUN_STATUS_TIMEOUT = "timeout"
LLM_RUN_STATUSES = {
    LLM_RUN_STATUS_SUCCESS,
    LLM_RUN_STATUS_REFUSAL,
    LLM_RUN_STATUS_PARSE_ERROR,
    LLM_RUN_STATUS_API_ERROR,
    LLM_RUN_STATUS_TIMEOUT,
}


def empty_meta() -> Dict[str, Any]:
    return {
        "last_commit": None,
        "total_commits": None,
        "git_history": [],
    }


def empty_interrelations() -> Dict[str, List[Any]]:
    return {
        "preamble_extracted": [],
        "body_extracted_regex": [],
        "body_extracted_llm": [],
    }


def empty_insights() -> Dict[str, Any]:
    return {
        "formal_compliance": {},
        "word_list": {},
        "changes_in_status": [],
        "interrelations": empty_interrelations(),
    }


def _as_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _has_value(value: Any) -> bool:
    return value not in (None, "", [], {})


def get_preamble_interrelations(
    preamble: Dict[str, Any] | None,
    source_context: SourceContext | None = None,
) -> Dict[str, Any]:
    source = _as_dict(preamble)
    context = source_context or SourceContext.default()
    field_aliases = context.field_aliases
    interrelation_types = context.preamble_interrelation_types
    interrelations: Dict[str, Any] = {}

    for subtype in interrelation_types:
        value = source.get(subtype)
        if not _has_value(value):
            for source_key, canonical_key in field_aliases.items():
                if canonical_key != subtype:
                    continue
                alias_value = source.get(source_key)
                if _has_value(alias_value):
                    value = alias_value
                    break
        if _has_value(value):
            interrelations[subtype] = value

    return interrelations


def normalize_raw_preamble(
    preamble: Dict[str, Any] | None,
    source_context: SourceContext | None = None,
) -> Dict[str, Any]:
    normalized = _as_dict(preamble)
    field_aliases = (source_context or SourceContext.default()).field_aliases

    for source_key, canonical_key in field_aliases.items():
        if canonical_key in normalized:
            continue
        if source_key not in normalized:
            continue
        normalized[canonical_key] = normalized[source_key]

    for source_key, canonical_key in field_aliases.items():
        if canonical_key != source_key:
            normalized.pop(source_key, None)

    return normalized


def get_meta(proposal: Dict[str, Any]) -> Dict[str, Any]:
    meta = empty_meta()
    canonical_meta = _as_dict(proposal.get("meta"))

    for key in META_KEYS:
        if key in canonical_meta:
            meta[key] = canonical_meta[key]

    if not isinstance(meta["git_history"], list):
        meta["git_history"] = []

    return meta


def get_formal_compliance(proposal: Dict[str, Any]) -> Dict[str, Any]:
    insights = _as_dict(proposal.get("insights"))
    candidate = insights.get("formal_compliance")
    return dict(candidate) if isinstance(candidate, dict) else {}


def get_changes_in_status(proposal: Dict[str, Any]) -> List[Any]:
    insights = _as_dict(proposal.get("insights"))
    candidate = insights.get("changes_in_status")
    return list(candidate) if isinstance(candidate, list) else []


def is_llm_runs_format(value: Any) -> bool:
    """Return True when value is the timestamped multi-run list format for body_extracted_llm."""
    return (
        isinstance(value, list)
        and bool(value)
        and isinstance(value[0], dict)
        and "timestamp" in value[0]
        and "dependencies" in value[0]
    )


def llm_run_status(run: Dict[str, Any] | Any) -> str:
    if not isinstance(run, dict):
        return ""
    status = str(run.get("status") or "").strip().lower()
    if status:
        return status
    # Legacy runs without an explicit status are treated as successful.
    if "timestamp" in run and "dependencies" in run:
        return LLM_RUN_STATUS_SUCCESS
    return ""


def is_successful_llm_run(run: Dict[str, Any] | Any) -> bool:
    return llm_run_status(run) == LLM_RUN_STATUS_SUCCESS


def latest_llm_run(value: Any) -> Dict[str, Any] | None:
    if not isinstance(value, list) or not value or not is_llm_runs_format(value):
        return None
    return max(value, key=lambda r: str(r.get("timestamp", "")))


def latest_llm_dependencies(value: Any) -> List[Any]:
    """Resolve body_extracted_llm to the latest run's dependency list."""
    latest = latest_llm_run(value)
    if latest is not None:
        if not is_successful_llm_run(latest):
            return []
        return list(latest.get("dependencies") or [])
    return []


def normalize_interrelations(proposal: Dict[str, Any]) -> Dict[str, Any]:
    interrelations = empty_interrelations()
    insights = _as_dict(proposal.get("insights"))
    canonical = _as_dict(insights.get("interrelations"))

    preamble_extracted = canonical.get("preamble_extracted")
    if isinstance(preamble_extracted, list):
        interrelations["preamble_extracted"] = list(preamble_extracted)

    body_extracted_regex = canonical.get("body_extracted_regex")
    if isinstance(body_extracted_regex, list):
        interrelations["body_extracted_regex"] = list(body_extracted_regex)

    body_extracted_llm = canonical.get("body_extracted_llm")
    if is_llm_runs_format(body_extracted_llm):
        interrelations["body_extracted_llm"] = list(body_extracted_llm)

    return interrelations


def get_interrelations(proposal: Dict[str, Any]) -> Dict[str, Any]:
    interrelations = normalize_interrelations(proposal)
    interrelations["body_extracted_llm"] = latest_llm_dependencies(
        interrelations["body_extracted_llm"]
    )
    return interrelations


def normalize_proposal_document(
    proposal: Dict[str, Any] | None,
    source_context: SourceContext | None = None,
) -> Dict[str, Any]:
    source = proposal if isinstance(proposal, dict) else {}
    raw = _as_dict(source.get("raw"))
    insights = _as_dict(source.get("insights"))

    normalized_raw: Dict[str, Any] = {
        "preamble": normalize_raw_preamble(
            raw.get("preamble"), source_context=source_context
        ),
    }
    for key, value in raw.items():
        if key in {"preamble", "compliance"}:
            continue
        normalized_raw[key] = value

    normalized_insights = empty_insights()
    for key, value in insights.items():
        if key in {"formal_compliance", "changes_in_status", "interrelations"}:
            continue
        if key in OBSOLETE_INTERRELATION_KEYS:
            continue
        normalized_insights[key] = value

    word_list = insights.get("word_list")
    normalized_insights["word_list"] = (
        dict(word_list) if isinstance(word_list, dict) else {}
    )
    normalized_insights["formal_compliance"] = get_formal_compliance(source)
    normalized_insights["changes_in_status"] = get_changes_in_status(source)
    normalized_insights["interrelations"] = normalize_interrelations(source)

    normalized = {
        "raw": normalized_raw,
        "meta": get_meta(source),
        "insights": normalized_insights,
    }

    for key, value in source.items():
        if key in {"raw", "meta", "insights"} or key in LEGACY_TOP_LEVEL_KEYS:
            continue
        normalized[key] = value

    return normalized
