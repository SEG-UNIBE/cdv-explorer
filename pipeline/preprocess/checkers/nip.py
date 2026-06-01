"""Compliance checker for Nostr Implementation Possibilities (NIPs)."""
from typing import Any, Dict, List


def check(preamble: Dict[str, Any], content: str, src_config: dict) -> List[dict]:
    """Return a flat list of compliance checks for a single NIP document."""
    from analysis.conformity.compliance import (
        _make_check,
        _has_value,
        _extract_section_entries,
        _normalize_section_name,
    )

    standard: str = src_config.get("document_prefix", "nip")
    preamble_config = src_config["preamble"]
    required_fields: list = preamble_config["required_fields"]
    expected_headlines: dict = preamble_config["expected_headlines"]

    checks: List[dict] = []

    # Required field presence
    for field in required_fields:
        value = preamble.get(field)
        checks.append(_make_check(
            f"{standard}.required_field.{field}",
            f"Required field '{field}' is present",
            _has_value(value),
            category="required_field",
            standard=standard,
            details=None if _has_value(value) else f"Missing required field '{field}'",
        ))

    # Expected section headings
    found = {e["normalized_name"]: e["level"] for e in _extract_section_entries(content)}
    for heading, expected_level in expected_headlines.items():
        normalized = _normalize_section_name(heading)
        actual_level = found.get(normalized)
        passed = actual_level == expected_level
        details = None
        if actual_level is None:
            details = f"Missing heading '{heading}'"
        elif not passed:
            details = f"Expected level {expected_level}, found level {actual_level}"
        checks.append(_make_check(
            f"{standard}.heading.{normalized.replace(' ', '_')}",
            f"Heading '{heading}' exists at level {expected_level}",
            passed,
            category="heading",
            standard=standard,
            details=details,
        ))

    # Soft check: type tag (mandatory / optional) is present
    checks.append(_make_check(
        f"{standard}.field_present.type",
        "Classification tag 'type' (mandatory/optional) is present",
        _has_value(preamble.get("type")),
        category="field_present",
        standard=standard,
        details=None if _has_value(preamble.get("type")) else "Tag 'type' not found",
    ))

    return checks
