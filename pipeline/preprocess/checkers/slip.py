"""Compliance checker for SatoshiLabs Improvement Proposals (SLIPs)."""
from typing import Any, Dict, List

from analysis.conformity.compliance import check_headlines, check_required_fields


def _make_check(
    check_id: str,
    label: str,
    passed: bool,
    *,
    category: str,
    details: str | None = None,
) -> Dict[str, Any]:
    return {
        "id": check_id,
        "label": label,
        "category": category,
        "standard": "slip",
        "passed": passed,
        "details": details,
    }


def check(preamble: Dict[str, Any], content: str, src_config: dict) -> List[dict]:
    preamble_config = src_config["preamble"]
    required_fields: list = preamble_config["required_fields"]
    expected_headlines: dict = preamble_config.get("expected_headlines", {})

    missing_fields = set(check_required_fields(preamble, required_fields))
    checks: List[dict] = [
        _make_check(
            f"slip.required_field.{field}",
            f"Required field '{field}' is present",
            field not in missing_fields,
            category="required_field",
            details=None if field not in missing_fields else f"Missing required field '{field}'",
        )
        for field in required_fields
    ]

    headline_issues = check_headlines(content, expected_headlines)
    for heading, expected_level in expected_headlines.items():
        issue = next((item for item in headline_issues if heading in item), None)
        checks.append(
            _make_check(
                f"slip.heading.{heading.replace(' ', '_')}",
                f"Heading '{heading}' exists at level {expected_level}",
                issue is None,
                category="heading",
                details=issue,
            )
        )

    return checks
