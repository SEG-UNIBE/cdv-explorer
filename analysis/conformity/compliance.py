import re
from datetime import date
from typing import Any, Dict, List


SECTION_PATTERN = re.compile(r"^(={2,6})\s*(.+?)\s*\1\s*$", re.MULTILINE)
PREAMBLE_LINE_PATTERN = re.compile(r"^\s*([A-Za-z][A-Za-z0-9-]*):\s*(.*)$")
EMAIL_ENTITY_PATTERN = re.compile(r"^.+ <[^<>\s@]+@[^<>\s@]+>$")
INTEGER_OR_QUESTION_PATTERN = re.compile(r"^(?:0|[1-9]\d*|\?)$")
SEMVER_PATTERN = re.compile(r"\b(\d+)\.(\d+)\.(\d+)\b")
DISCUSSION_LINE_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2}): (\S+)$")
BIP_LIST_PATTERN = re.compile(r"^(?:0|[1-9]\d*)(?:, (?:0|[1-9]\d*))*$")

BIP3_HEADER_ORDER = [
    "bip",
    "layer",
    "title",
    "authors",
    "deputies",
    "status",
    "type",
    "assigned",
    "license",
    "discussion",
    "version",
    "requires",
    "replaces",
    "proposed_replacement",
]
BIP3_REQUIRED_HEADERS = ["bip", "title", "authors", "status", "type", "assigned", "license"]
BIP3_REQUIRED_SECTIONS = ["abstract", "motivation", "copyright"]
BIP3_ALLOWED_STATUSES = {"Draft", "Complete", "Deployed", "Closed"}
BIP3_ALLOWED_TYPES = {"Specification", "Informational", "Process"}
SECTION_NAME_ALIASES = {"change log": "changelog"}


def _make_check(
    check_id: str,
    label: str,
    passed: bool | None,
    *,
    category: str,
    standard: str,
    details: str | None = None,
) -> Dict[str, Any]:
    return {
        "id": check_id,
        "label": label,
        "category": category,
        "standard": standard,
        "passed": passed,
        "details": details,
    }


def _summarize_checks(checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    passed_checks = sum(1 for check in checks if check.get("passed") is True)
    failed_checks = sum(1 for check in checks if check.get("passed") is False)
    skipped_checks = sum(1 for check in checks if check.get("passed") is None)
    total_checks = passed_checks + failed_checks
    score = round((passed_checks / total_checks) * 100, 2) if total_checks else None
    return {
        "score": score,
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "skipped_checks": skipped_checks,
        "total_checks": total_checks,
        "checks": checks,
    }


def _normalize_section_name(name: str) -> str:
    normalized = " ".join(name.strip().lower().split())
    return SECTION_NAME_ALIASES.get(normalized, normalized)


def _normalize_header_name(name: str) -> str:
    return name.strip().lower().replace("-", "_")


def _is_valid_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _extract_section_entries(file_content: str) -> List[Dict[str, Any]]:
    matches = list(SECTION_PATTERN.finditer(file_content))
    entries: List[Dict[str, Any]] = []

    for index, match in enumerate(matches):
        body_start = match.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(file_content)
        entries.append(
            {
                "name": match.group(2).strip(),
                "normalized_name": _normalize_section_name(match.group(2)),
                "level": len(match.group(1)),
                "body": file_content[body_start:body_end].strip(),
            }
        )

    return entries


def _extract_section_map(file_content: str) -> Dict[str, Dict[str, Any]]:
    section_map: Dict[str, Dict[str, Any]] = {}
    for entry in _extract_section_entries(file_content):
        section_map.setdefault(entry["normalized_name"], entry)
    return section_map


def _extract_top_preamble_block(file_content: str) -> str | None:
    content = file_content.lstrip("\ufeff")
    pre_match = re.match(r"\s*<pre>\s*\n?(.*?)\n?\s*</pre>", content, re.DOTALL)
    if pre_match:
        return pre_match.group(1)

    lines = content.splitlines()
    block_lines: List[str] = []
    started = False

    for line in lines:
        if not started and not line.strip():
            continue

        if not started:
            if PREAMBLE_LINE_PATTERN.match(line):
                started = True
                block_lines.append(line)
            else:
                return None
            continue

        if not line.strip():
            break

        if PREAMBLE_LINE_PATTERN.match(line) or re.match(r"^\s+\S", line):
            block_lines.append(line)
            continue

        break

    return "\n".join(block_lines) if block_lines else None


def _parse_top_rfc822_preamble(file_content: str) -> Dict[str, Any]:
    block = _extract_top_preamble_block(file_content)
    if not block:
        return {"exists": False, "valid": False, "headers": [], "headers_by_name": {}}

    headers: List[Dict[str, Any]] = []
    current_name: str | None = None
    current_value_lines: List[str] = []
    valid = True

    for raw_line in block.splitlines():
        if not raw_line.strip():
            continue

        header_match = PREAMBLE_LINE_PATTERN.match(raw_line)
        if header_match:
            if current_name is not None:
                header_name = current_name
                normalized_name = _normalize_header_name(header_name)
                headers.append(
                    {
                        "name": header_name,
                        "normalized_name": normalized_name,
                        "value": "\n".join(current_value_lines).strip(),
                    }
                )

            current_name = header_match.group(1).strip()
            current_value_lines = [header_match.group(2).strip()]
            continue

        if current_name is not None and re.match(r"^\s+\S", raw_line):
            current_value_lines.append(raw_line.strip())
            continue

        valid = False

    if current_name is not None:
        header_name = current_name
        normalized_name = _normalize_header_name(header_name)
        headers.append(
            {
                "name": header_name,
                "normalized_name": normalized_name,
                "value": "\n".join(current_value_lines).strip(),
            }
        )

    headers_by_name: Dict[str, List[Dict[str, Any]]] = {}
    for header in headers:
        headers_by_name.setdefault(header["normalized_name"], []).append(header)

    return {
        "exists": bool(headers),
        "valid": valid and bool(headers),
        "headers": headers,
        "headers_by_name": headers_by_name,
    }


def _get_first_header_value(headers_by_name: Dict[str, List[Dict[str, Any]]], name: str) -> str | None:
    entries = headers_by_name.get(name) or []
    if not entries:
        return None
    return entries[0].get("value")


def _validate_email_entities(value: str) -> bool:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    return bool(lines) and all(EMAIL_ENTITY_PATTERN.match(line) for line in lines)


def _validate_bip_number_list(value: str) -> bool:
    return bool(value) and bool(BIP_LIST_PATTERN.fullmatch(value.strip()))


def _extract_latest_semver(text: str) -> str | None:
    versions = [tuple(int(part) for part in match.groups()) for match in SEMVER_PATTERN.finditer(text)]
    if not versions:
        return None
    latest = max(versions)
    return ".".join(str(part) for part in latest)


def _has_value(value: Any) -> bool:
    return value not in (None, "", [])


def check_required_fields(preamble: Dict[str, str], required_fields: List[str]) -> List[str]:
    return [field for field in required_fields if not _has_value(preamble.get(field))]


def check_headlines(file_content: str, expected_headlines: Dict[str, int]) -> List[str]:
    found_headings = {
        entry["normalized_name"]: entry["level"] for entry in _extract_section_entries(file_content)
    }

    issues = []
    for expected_heading, expected_level in expected_headlines.items():
        normalized_heading = _normalize_section_name(expected_heading)
        actual_level = found_headings.get(normalized_heading)
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
    score = assess_bip2_compliance(
        preamble,
        file_content,
        required_fields=required_fields,
        expected_headlines=expected_headlines,
    )["score"]
    preamble["Compliance Score"] = round(score, 2)
    return score


def add_missing_optional_fields(preamble: Dict[str, str], optional_fields: List[str]) -> None:
    for field in optional_fields:
        if field not in preamble:
            preamble[field] = None


def assess_bip2_compliance(
    preamble: Dict[str, Any],
    file_content: str,
    *,
    required_fields: List[str],
    expected_headlines: Dict[str, int],
) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    for field in required_fields:
        value = preamble.get(field)
        checks.append(
            _make_check(
                f"bip2.required_field.{field}",
                f"Required field '{field}' is present",
                _has_value(value),
                category="required_field",
                standard="bip2",
                details=None if _has_value(value) else f"Missing required field '{field}'",
            )
        )

    found_headings = {
        entry["normalized_name"]: entry["level"] for entry in _extract_section_entries(file_content)
    }
    for heading, expected_level in expected_headlines.items():
        normalized_heading = _normalize_section_name(heading)
        actual_level = found_headings.get(normalized_heading)
        passed = actual_level == expected_level
        details = None
        if actual_level is None:
            details = f"Missing heading '{heading}'"
        elif actual_level != expected_level:
            details = f"Expected level {expected_level}, found level {actual_level}"

        checks.append(
            _make_check(
                f"bip2.heading.{normalized_heading.replace(' ', '_')}",
                f"Heading '{heading}' exists at level {expected_level}",
                passed,
                category="heading",
                standard="bip2",
                details=details,
            )
        )

    return _summarize_checks(checks)


def assess_bip3_compliance(_preamble: Dict[str, Any], file_content: str) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    parsed_preamble = _parse_top_rfc822_preamble(file_content)
    headers = parsed_preamble["headers"]
    headers_by_name = parsed_preamble["headers_by_name"]
    section_map = _extract_section_map(file_content)

    checks.append(
        _make_check(
            "bip3.preamble.top_rfc822",
            "Preamble exists as RFC-822-style metadata at the top",
            parsed_preamble["valid"],
            category="preamble",
            standard="bip3",
            details=None if parsed_preamble["valid"] else "Missing or invalid top-of-file RFC-822-style preamble",
        )
    )

    for header in BIP3_REQUIRED_HEADERS:
        value = _get_first_header_value(headers_by_name, header)
        checks.append(
            _make_check(
                f"bip3.required_header.{header}",
                f"Required header '{header}' is present",
                bool(value),
                category="required_header",
                standard="bip3",
                details=None if value else f"Missing required header '{header}'",
            )
        )

    known_headers = [header["normalized_name"] for header in headers if header["normalized_name"] in BIP3_HEADER_ORDER]
    order_indices = [BIP3_HEADER_ORDER.index(header_name) for header_name in known_headers]
    order_passed = parsed_preamble["valid"] and order_indices == sorted(order_indices) and len(known_headers) == len(set(known_headers))
    checks.append(
        _make_check(
            "bip3.header_order",
            "Headers appear in the expected BIP3 order",
            order_passed,
            category="header_order",
            standard="bip3",
            details=None if order_passed else "Recognized BIP3 headers are out of order or duplicated",
        )
    )

    bip_value = _get_first_header_value(headers_by_name, "bip")
    checks.append(
        _make_check(
            "bip3.header_value.bip",
            "Header 'BIP' is an integer without leading zeros or '?'",
            None if bip_value is None else bool(INTEGER_OR_QUESTION_PATTERN.fullmatch(bip_value.strip())),
            category="header_value",
            standard="bip3",
            details=None if bip_value is None or INTEGER_OR_QUESTION_PATTERN.fullmatch(bip_value.strip()) else f"Invalid BIP value '{bip_value}'",
        )
    )

    title_value = _get_first_header_value(headers_by_name, "title")
    checks.append(
        _make_check(
            "bip3.header_value.title",
            "Header 'Title' is 50 characters or fewer",
            None if title_value is None else len(title_value.strip()) <= 50,
            category="header_value",
            standard="bip3",
            details=None if title_value is None or len(title_value.strip()) <= 50 else f"Title length is {len(title_value.strip())}, expected <= 50",
        )
    )

    for header_name in ("authors", "deputies"):
        header_value = _get_first_header_value(headers_by_name, header_name)
        checks.append(
            _make_check(
                f"bip3.header_value.{header_name}",
                f"Header '{header_name}' uses 'Name <email>' entries",
                None if header_value is None else _validate_email_entities(header_value),
                category="header_value",
                standard="bip3",
                details=None if header_value is None or _validate_email_entities(header_value) else f"Invalid {header_name} value",
            )
        )

    status_value = _get_first_header_value(headers_by_name, "status")
    checks.append(
        _make_check(
            "bip3.header_value.status",
            "Header 'Status' is one of Draft, Complete, Deployed, Closed",
            None if status_value is None else status_value.strip() in BIP3_ALLOWED_STATUSES,
            category="header_value",
            standard="bip3",
            details=None if status_value is None or status_value.strip() in BIP3_ALLOWED_STATUSES else f"Invalid Status '{status_value}'",
        )
    )

    type_value = _get_first_header_value(headers_by_name, "type")
    checks.append(
        _make_check(
            "bip3.header_value.type",
            "Header 'Type' is one of Specification, Informational, Process",
            None if type_value is None else type_value.strip() in BIP3_ALLOWED_TYPES,
            category="header_value",
            standard="bip3",
            details=None if type_value is None or type_value.strip() in BIP3_ALLOWED_TYPES else f"Invalid Type '{type_value}'",
        )
    )

    assigned_value = _get_first_header_value(headers_by_name, "assigned")
    assigned_passed = None
    if assigned_value is not None:
        assigned_text = assigned_value.strip()
        assigned_passed = assigned_text == "?" or _is_valid_iso_date(assigned_text)
    checks.append(
        _make_check(
            "bip3.header_value.assigned",
            "Header 'Assigned' is yyyy-mm-dd or '?'",
            assigned_passed,
            category="header_value",
            standard="bip3",
            details=None if assigned_passed is not False else f"Invalid Assigned value '{assigned_value}'",
        )
    )

    license_value = _get_first_header_value(headers_by_name, "license")
    checks.append(
        _make_check(
            "bip3.header_value.license",
            "Header 'License' is non-empty",
            None if license_value is None else bool(license_value.strip()),
            category="header_value",
            standard="bip3",
            details=None if license_value is None or license_value.strip() else "License is empty",
        )
    )

    discussion_value = _get_first_header_value(headers_by_name, "discussion")
    discussion_passed = None
    discussion_details = None
    if discussion_value is not None:
        discussion_lines = [line.strip() for line in discussion_value.splitlines() if line.strip()]
        discussion_passed = bool(discussion_lines)
        if discussion_passed:
            for discussion_line in discussion_lines:
                discussion_match = DISCUSSION_LINE_PATTERN.fullmatch(discussion_line)
                if not discussion_match or not _is_valid_iso_date(discussion_match.group(1)):
                    discussion_passed = False
                    discussion_details = f"Invalid Discussion entry '{discussion_line}'"
                    break
        if discussion_passed and discussion_details is None:
            discussion_details = None
    checks.append(
        _make_check(
            "bip3.header_value.discussion",
            "Header 'Discussion' uses 'yyyy-mm-dd: URL' lines",
            discussion_passed,
            category="header_value",
            standard="bip3",
            details=discussion_details,
        )
    )

    version_value = _get_first_header_value(headers_by_name, "version")
    checks.append(
        _make_check(
            "bip3.header_value.version",
            "Header 'Version' uses MAJOR.MINOR.PATCH",
            None if version_value is None else bool(SEMVER_PATTERN.fullmatch(version_value.strip())),
            category="header_value",
            standard="bip3",
            details=None if version_value is None or SEMVER_PATTERN.fullmatch(version_value.strip()) else f"Invalid Version '{version_value}'",
        )
    )

    for header_name in ("requires", "replaces", "proposed_replacement"):
        header_value = _get_first_header_value(headers_by_name, header_name)
        checks.append(
            _make_check(
                f"bip3.header_value.{header_name}",
                f"Header '{header_name}' uses comma+space separated BIP numbers",
                None if header_value is None else _validate_bip_number_list(header_value.strip()),
                category="header_value",
                standard="bip3",
                details=None if header_value is None or _validate_bip_number_list(header_value.strip()) else f"Invalid {header_name} value '{header_value}'",
            )
        )

    for section_name in BIP3_REQUIRED_SECTIONS:
        checks.append(
            _make_check(
                f"bip3.required_section.{section_name}",
                f"Required section '{section_name}' is present",
                section_name in section_map,
                category="required_section",
                standard="bip3",
                details=None if section_name in section_map else f"Missing required section '{section_name}'",
            )
        )

    type_text = type_value.strip() if type_value else None
    specification_required = type_text == "Specification"
    checks.append(
        _make_check(
            "bip3.type_specific.specification_section",
            "Type 'Specification' includes a 'Specification' section",
            None if not specification_required else "specification" in section_map,
            category="type_specific",
            standard="bip3",
            details=None if not specification_required or "specification" in section_map else "Missing required section 'specification' for Type=Specification",
        )
    )

    status_text = status_value.strip() if status_value else None
    changelog_required = status_text in {"Complete", "Deployed"}
    changelog_section = section_map.get("changelog")
    latest_changelog_version = _extract_latest_semver(changelog_section["body"]) if changelog_section else None
    normalized_version = version_value.strip() if version_value else None

    checks.append(
        _make_check(
            "bip3.changelog.changelog_section",
            "Complete/Deployed proposals include a 'Changelog' section",
            None if not changelog_required else changelog_section is not None,
            category="changelog",
            standard="bip3",
            details=None if not changelog_required or changelog_section is not None else "Missing required 'changelog' section",
        )
    )
    checks.append(
        _make_check(
            "bip3.changelog.version_header",
            "Complete/Deployed proposals include a 'Version' header",
            None if not changelog_required else bool(normalized_version),
            category="changelog",
            standard="bip3",
            details=None if not changelog_required or normalized_version else "Missing required 'version' header",
        )
    )
    checks.append(
        _make_check(
            "bip3.changelog.version_matches",
            "Latest changelog version matches the 'Version' header",
            None
            if not changelog_required or not normalized_version
            else latest_changelog_version == normalized_version,
            category="changelog",
            standard="bip3",
            details=None
            if not changelog_required or not normalized_version or latest_changelog_version == normalized_version
            else (
                f"No semantic version found in changelog; expected '{normalized_version}'"
                if latest_changelog_version is None
                else f"Latest changelog version '{latest_changelog_version}' does not match Version '{normalized_version}'"
            ),
        )
    )

    return _summarize_checks(checks)


def assess_compliance(
    preamble: Dict[str, Any],
    file_content: str,
    *,
    required_fields: List[str],
    expected_headlines: Dict[str, int],
) -> Dict[str, Any]:
    bip2 = assess_bip2_compliance(
        preamble,
        file_content,
        required_fields=required_fields,
        expected_headlines=expected_headlines,
    )
    bip3 = assess_bip3_compliance(preamble, file_content)
    combined_summary = _summarize_checks([*bip2["checks"], *bip3["checks"]])

    return {
        "score": combined_summary["score"],
        "passed_checks": combined_summary["passed_checks"],
        "failed_checks": combined_summary["failed_checks"],
        "skipped_checks": combined_summary["skipped_checks"],
        "total_checks": combined_summary["total_checks"],
        "bip2": bip2,
        "bip3": bip3,
    }
