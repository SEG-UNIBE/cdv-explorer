import re
from typing import Dict, List


def check_required_fields(preamble: Dict[str, str], required_fields: List[str]) -> List[str]:
    return [field for field in required_fields if field not in preamble]


def check_headlines(file_content: str, expected_headlines: Dict[str, int]) -> List[str]:
    pattern = r"^(={2,6})\s*(.+?)\s*\1$"
    matches = re.findall(pattern, file_content, re.MULTILINE)

    found_headings = {
        heading.strip().lower(): len(eq)
        for eq, heading in matches
    }

    issues = []
    for expected_heading, expected_level in expected_headlines.items():
        actual_level = found_headings.get(expected_heading)
        if actual_level is None:
            issues.append(f"Missing: {expected_heading}")
        elif actual_level != expected_level:
            issues.append(f"Wrong level for {expected_heading}: expected {expected_level}, found {actual_level}")

    return issues


def calculate_compliance_score(
    preamble: Dict[str, str],
    file_content: str,
    required_fields: List[str],
    expected_headlines: Dict[str, int],
) -> float:
    required_issues = check_required_fields(preamble, required_fields)
    headline_issues = check_headlines(file_content, expected_headlines)

    total_checks = len(required_fields) + len(expected_headlines)
    failed_checks = len(required_issues) + len(headline_issues)
    passed_checks = total_checks - failed_checks

    score = (passed_checks / total_checks) * 100
    preamble["Compliance Score"] = round(score, 2)
    return score


def add_missing_optional_fields(preamble: Dict[str, str], optional_fields: List[str]) -> None:
    for field in optional_fields:
        if field not in preamble:
            preamble[field] = None
