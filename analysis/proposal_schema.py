from typing import Any, Dict, List

from pipeline.ecosystem_config import ACTIVE_ECOSYSTEM


META_KEYS = ("last_commit", "total_commits", "git_history")
INTERRELATION_KEY_MAP = {
    "preamble_extracted": "explicit_dependencies",
    "body_extracted_regex": "explicit_references",
    "body_extracted_llm": "implicit_dependencies",
}
LEGACY_TOP_LEVEL_KEYS = {"metadata", "history", "compliance"}
PREAMBLE_FIELD_ALIASES = ACTIVE_ECOSYSTEM.get("preamble", {}).get("field_aliases", {})
PREAMBLE_INTERRELATION_KEYS = ("requires", "replaces", "proposed_replacement")


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


def get_preamble_interrelations(preamble: Dict[str, Any] | None) -> Dict[str, Any]:
    source = _as_dict(preamble)
    interrelations: Dict[str, Any] = {}

    for subtype in PREAMBLE_INTERRELATION_KEYS:
        value = source.get(subtype)
        if not _has_value(value):
            for source_key, canonical_key in PREAMBLE_FIELD_ALIASES.items():
                if canonical_key != subtype:
                    continue
                alias_value = source.get(source_key)
                if _has_value(alias_value):
                    value = alias_value
                    break
        if _has_value(value):
            interrelations[subtype] = value

    return interrelations


def normalize_raw_preamble(preamble: Dict[str, Any] | None) -> Dict[str, Any]:
    normalized = _as_dict(preamble)

    for source_key, canonical_key in PREAMBLE_FIELD_ALIASES.items():
        if canonical_key in normalized:
            continue
        if source_key not in normalized:
            continue
        normalized[canonical_key] = normalized[source_key]

    for source_key, canonical_key in PREAMBLE_FIELD_ALIASES.items():
        if canonical_key != source_key:
            normalized.pop(source_key, None)

    return normalized


def get_meta(proposal: Dict[str, Any]) -> Dict[str, Any]:
    meta = empty_meta()
    legacy_meta = _as_dict(proposal.get("metadata"))
    canonical_meta = _as_dict(proposal.get("meta"))

    for source in (legacy_meta, canonical_meta):
        for key in META_KEYS:
            if key in source:
                meta[key] = source[key]

    if not isinstance(meta["git_history"], list):
        meta["git_history"] = []

    return meta


def get_formal_compliance(proposal: Dict[str, Any]) -> Dict[str, Any]:
    raw = _as_dict(proposal.get("raw"))
    insights = _as_dict(proposal.get("insights"))

    for candidate in (
        insights.get("formal_compliance"),
        proposal.get("compliance"),
        raw.get("compliance"),
    ):
        if isinstance(candidate, dict):
            return dict(candidate)

    return {}


def get_changes_in_status(proposal: Dict[str, Any]) -> List[Any]:
    legacy_history = _as_dict(proposal.get("history"))
    insights = _as_dict(proposal.get("insights"))

    for candidate in (
        insights.get("changes_in_status"),
        legacy_history.get("status_timeline"),
    ):
        if isinstance(candidate, list):
            return list(candidate)

    return []


def get_interrelations(proposal: Dict[str, Any]) -> Dict[str, List[Any]]:
    interrelations = empty_interrelations()
    insights = _as_dict(proposal.get("insights"))
    canonical = _as_dict(insights.get("interrelations"))

    for canonical_key, legacy_key in INTERRELATION_KEY_MAP.items():
        legacy_value = insights.get(legacy_key)
        canonical_value = canonical.get(canonical_key)

        if isinstance(legacy_value, list):
            interrelations[canonical_key] = list(legacy_value)
        if isinstance(canonical_value, list):
            interrelations[canonical_key] = list(canonical_value)

    return interrelations


def normalize_proposal_document(proposal: Dict[str, Any] | None) -> Dict[str, Any]:
    source = proposal if isinstance(proposal, dict) else {}
    raw = _as_dict(source.get("raw"))
    insights = _as_dict(source.get("insights"))

    normalized_raw: Dict[str, Any] = {
        "preamble": normalize_raw_preamble(raw.get("preamble")),
    }
    for key, value in raw.items():
        if key in {"preamble", "compliance"}:
            continue
        normalized_raw[key] = value

    normalized_insights = empty_insights()
    for key, value in insights.items():
        if key in {"formal_compliance", "changes_in_status", "interrelations"}:
            continue
        if key in INTERRELATION_KEY_MAP.values():
            continue
        normalized_insights[key] = value

    word_list = insights.get("word_list")
    normalized_insights["word_list"] = dict(word_list) if isinstance(word_list, dict) else {}
    normalized_insights["formal_compliance"] = get_formal_compliance(source)
    normalized_insights["changes_in_status"] = get_changes_in_status(source)
    normalized_insights["interrelations"] = get_interrelations(source)

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
