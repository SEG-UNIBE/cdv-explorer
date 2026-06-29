from __future__ import annotations

import csv
import io
import re
import zipfile
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence
from xml.etree import ElementTree as ET

from analysis.reference_ids import normalize_reference_id_for_config


GROUND_TRUTH_WORKBOOK_FILENAME = "ground_truth.xlsx"


GROUND_TRUTH_CSV_COLUMNS = (
    "source",
    "target",
    "relation_type",
    "confidence",
    "evidence",
    "note",
    "reviewer",
    "reviewed_at",
)
REVIEWED_IPS_CSV_COLUMNS = (
    "ip",
    "reviewer",
    "reviewed_at",
    "sampling_strategy",
    "sampling_snapshot",
    "sampling_seed",
    "era_bucket",
    "density_bucket",
    "density_basis",
    "created",
    "status",
    "type",
    "layer",
    "title",
    "extracted_target_count",
    "note",
)
GROUND_TRUTH_ALLOWED_RELATION_TYPES = {
    "depends_on",
    "supersedes",
    "superseded_by",
    "references",
}
GROUND_TRUTH_ALLOWED_CONFIDENCE = {"low", "medium", "high"}
REVIEWED_IP_ALLOWED_SAMPLING_STRATEGIES = {"sampler", "manual"}
REVIEWED_IP_ALLOWED_DENSITY_BUCKETS = {"none", "low", "high"}
REVIEWED_IP_ALLOWED_DENSITY_BASIS = {
    "all_methods",
    "regex_only",
    "llm_only",
    "preamble_only",
}
GROUND_TRUTH_GRAPH_KEY_RE = re.compile(r"^(?P<source>[A-Za-z0-9_-]+):(?P<id>[^:\s]+)$")
GROUND_TRUTH_REVIEW_POLICIES: dict[str, dict[str, Any]] = {
    "bitcoin": {
        "allowed_source_slugs": ("bips",),
        "required_type": "Specification",
    },
}
GROUND_TRUTH_WORKBOOK_SHEETS = (
    ("ips", REVIEWED_IPS_CSV_COLUMNS),
    ("interrelations", GROUND_TRUTH_CSV_COLUMNS),
)
_XLSX_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_XLSX_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_XLSX_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_XLSX_NAMESPACES = {"x": _XLSX_MAIN_NS, "r": _XLSX_REL_NS, "pr": _XLSX_PKG_REL_NS}


def ground_truth_directory(ecosystem_slug: str | None) -> Path:
    return Path("ip_data") / str(ecosystem_slug) / "ground_truth"


def ground_truth_workbook_path(ecosystem_slug: str | None) -> Path:
    return ground_truth_directory(ecosystem_slug) / GROUND_TRUTH_WORKBOOK_FILENAME


def _ground_truth_csv_path(ecosystem_slug: str | None, sheet_name: str) -> Path:
    if sheet_name == "ips":
        filename = "ips.csv"
    elif sheet_name == "interrelations":
        filename = "interrelations.csv"
    else:
        raise ValueError(f"Unknown ground-truth sheet `{sheet_name}`")
    return ground_truth_directory(ecosystem_slug) / filename


def _excel_column_name(index: int) -> str:
    value = index + 1
    name = ""
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        name = chr(ord("A") + remainder) + name
    return name


def _excel_column_index(cell_ref: str) -> int:
    letters = []
    for char in str(cell_ref or ""):
        if char.isalpha():
            letters.append(char.upper())
        else:
            break
    if not letters:
        return 0
    value = 0
    for char in letters:
        value = (value * 26) + (ord(char) - ord("A") + 1)
    return max(value - 1, 0)


def _append_inline_string_cell(
    row_element: ET.Element,
    *,
    row_number: int,
    column_index: int,
    value: str,
) -> None:
    if value == "":
        return
    cell = ET.SubElement(
        row_element,
        f"{{{_XLSX_MAIN_NS}}}c",
        {
            "r": f"{_excel_column_name(column_index)}{row_number}",
            "t": "inlineStr",
        },
    )
    inline_string = ET.SubElement(cell, f"{{{_XLSX_MAIN_NS}}}is")
    text = ET.SubElement(inline_string, f"{{{_XLSX_MAIN_NS}}}t")
    if value[:1].isspace() or value[-1:].isspace():
        text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    text.text = value


def _build_sheet_xml(columns: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> bytes:
    worksheet = ET.Element(
        f"{{{_XLSX_MAIN_NS}}}worksheet",
        {"xmlns": _XLSX_MAIN_NS},
    )
    sheet_data = ET.SubElement(worksheet, f"{{{_XLSX_MAIN_NS}}}sheetData")

    header_row = ET.SubElement(
        sheet_data,
        f"{{{_XLSX_MAIN_NS}}}row",
        {"r": "1"},
    )
    for index, column in enumerate(columns):
        _append_inline_string_cell(
            header_row,
            row_number=1,
            column_index=index,
            value=str(column),
        )

    for row_number, row in enumerate(rows, start=2):
        row_element = ET.SubElement(
            sheet_data,
            f"{{{_XLSX_MAIN_NS}}}row",
            {"r": str(row_number)},
        )
        for index, column in enumerate(columns):
            _append_inline_string_cell(
                row_element,
                row_number=row_number,
                column_index=index,
                value=str(row.get(column, "") or ""),
            )

    return ET.tostring(worksheet, encoding="utf-8", xml_declaration=True)


def _sheet_value_from_cell(
    cell: ET.Element,
    *,
    shared_strings: Sequence[str],
    column_name: str | None = None,
) -> str:
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        return "".join(cell.itertext()).strip()
    if cell_type == "s":
        raw_index = cell.findtext("x:v", default="", namespaces=_XLSX_NAMESPACES).strip()
        if raw_index.isdigit():
            index = int(raw_index)
            if 0 <= index < len(shared_strings):
                return shared_strings[index].strip()
        return ""

    value = cell.findtext("x:v", default="", namespaces=_XLSX_NAMESPACES).strip()
    if value and column_name in {"created", "reviewed_at"}:
        try:
            serial = float(value)
        except ValueError:
            return value
        if serial >= 1 and serial.is_integer():
            base = date(1899, 12, 30)
            return base.fromordinal(base.toordinal() + int(serial)).isoformat()
    return value


def _load_shared_strings(workbook: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    values: List[str] = []
    for string_item in root.findall("x:si", _XLSX_NAMESPACES):
        values.append("".join(string_item.itertext()))
    return values


def _sheet_path_by_name(workbook: zipfile.ZipFile, sheet_name: str) -> str:
    workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
    rels_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    targets_by_rel_id = {
        rel.get("Id"): rel.get("Target")
        for rel in rels_root.findall("pr:Relationship", _XLSX_NAMESPACES)
    }
    for sheet in workbook_root.findall("x:sheets/x:sheet", _XLSX_NAMESPACES):
        if str(sheet.get("name") or "").strip() != sheet_name:
            continue
        rel_id = sheet.get(f"{{{_XLSX_REL_NS}}}id")
        target = targets_by_rel_id.get(rel_id)
        if target:
            return f"xl/{target.lstrip('/')}"
    raise ValueError(f"Ground-truth workbook is missing sheet `{sheet_name}`")


def _load_xlsx_sheet_entries(
    workbook_path: Path,
    *,
    sheet_name: str,
    columns: Sequence[str],
) -> List[Dict[str, str]]:
    with zipfile.ZipFile(workbook_path) as workbook:
        shared_strings = _load_shared_strings(workbook)
        sheet_path = _sheet_path_by_name(workbook, sheet_name)
        sheet_root = ET.fromstring(workbook.read(sheet_path))

    rows: List[List[str]] = []
    for row_element in sheet_root.findall("x:sheetData/x:row", _XLSX_NAMESPACES):
        values_by_index: dict[int, str] = {}
        for cell in row_element.findall("x:c", _XLSX_NAMESPACES):
            cell_ref = str(cell.get("r") or "")
            column_index = _excel_column_index(cell_ref)
            values_by_index[column_index] = _sheet_value_from_cell(
                cell,
                shared_strings=shared_strings,
            )
        if not values_by_index:
            continue
        max_index = max(values_by_index)
        rows.append([values_by_index.get(index, "") for index in range(max_index + 1)])

    if not rows:
        return []

    header = [str(value or "").strip() for value in rows[0]]
    header_index = {name: index for index, name in enumerate(header) if name}
    missing = [column for column in columns if column not in header_index]
    if missing:
        raise ValueError(
            f"Ground-truth workbook sheet `{sheet_name}` is missing columns: {', '.join(missing)}"
        )

    entries: List[Dict[str, str]] = []
    for row_values in rows[1:]:
        entry = {
            column: str(row_values[header_index[column]]).strip()
            if header_index[column] < len(row_values)
            else ""
            for column in columns
        }
        if any(entry.values()):
            entries.append(entry)
    return entries


def _write_csv_rows(
    csv_path: Path,
    *,
    columns: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {column: str(row.get(column, "") or "") for column in columns}
            )


def sync_ground_truth_csvs_from_workbook(ecosystem_slug: str | None) -> bool:
    workbook_path = ground_truth_workbook_path(ecosystem_slug)
    if not workbook_path.exists():
        return False

    for sheet_name, columns in GROUND_TRUTH_WORKBOOK_SHEETS:
        rows = _load_xlsx_sheet_entries(
            workbook_path,
            sheet_name=sheet_name,
            columns=columns,
        )
        _write_csv_rows(
            _ground_truth_csv_path(ecosystem_slug, sheet_name),
            columns=columns,
            rows=rows,
        )
    return True


def ground_truth_source_configs_by_slug(
    ecosystem_slug: str | None,
) -> Dict[str, Dict[str, Any]]:
    if not ecosystem_slug:
        return {}

    from ecosystems import ECOSYSTEM_REGISTRY

    ecosystem = ECOSYSTEM_REGISTRY.get(str(ecosystem_slug), {})
    sources = ecosystem.get("sources", {}) if isinstance(ecosystem, Mapping) else {}
    configs: Dict[str, Dict[str, Any]] = {}
    for source_slug, source_config in sources.items():
        if not isinstance(source_config, Mapping):
            continue
        configs[str(source_slug)] = {
            "source_slug": str(source_slug),
            "proposal_label": source_config.get("proposal_acronym") or "IP",
            "reference_pattern": source_config.get("reference_pattern") or "",
            "max_proposal_id": source_config.get("max_proposal_id"),
        }
    return configs


def _validate_ground_truth_graph_key(
    value: Any,
    *,
    field_name: str,
    source_configs_by_slug: Mapping[str, Mapping[str, Any]],
) -> tuple[str, str]:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"missing `{field_name}`")

    match = GROUND_TRUTH_GRAPH_KEY_RE.match(text)
    if not match:
        raise ValueError(f"`{field_name}` must use source_slug:id format")

    source_slug = match.group("source")
    proposal_id = match.group("id")
    source_config = source_configs_by_slug.get(source_slug)
    if source_config is None:
        known = ", ".join(sorted(source_configs_by_slug)) or "none"
        raise ValueError(
            f"`{field_name}` uses unknown source slug `{source_slug}`; known sources: {known}"
        )

    normalized = normalize_reference_id_for_config(proposal_id, source_config)
    if normalized is None:
        raise ValueError(
            f"`{field_name}` has an invalid proposal id for source `{source_slug}`"
        )

    return source_slug, normalized


def validate_ground_truth_curated_entries(
    entries: Sequence[Mapping[str, Any]],
    *,
    source_configs_by_slug: Mapping[str, Mapping[str, Any]],
) -> List[str]:
    errors: List[str] = []
    seen_typed_edges: set[tuple[str, str, str]] = set()
    relation_types_by_pair: dict[tuple[str, str], str] = {}

    for index, entry in enumerate(entries):
        row_label = (
            f"row {entry.get('__line__')}"
            if isinstance(entry, Mapping) and entry.get("__line__")
            else f"row {index + 2}"
        )
        if not isinstance(entry, Mapping):
            errors.append(f"{row_label}: entry must be an object")
            continue

        row_errors: List[str] = []
        try:
            _validate_ground_truth_graph_key(
                entry.get("source"),
                field_name="source",
                source_configs_by_slug=source_configs_by_slug,
            )
        except ValueError as exc:
            row_errors.append(str(exc))
        try:
            _validate_ground_truth_graph_key(
                entry.get("target"),
                field_name="target",
                source_configs_by_slug=source_configs_by_slug,
            )
        except ValueError as exc:
            row_errors.append(str(exc))

        source = str(entry.get("source") or "").strip()
        target = str(entry.get("target") or "").strip()
        relation_type = str(entry.get("relation_type") or "").strip().lower()
        if not relation_type:
            row_errors.append("missing `relation_type`")
        elif relation_type not in GROUND_TRUTH_ALLOWED_RELATION_TYPES:
            allowed = ", ".join(sorted(GROUND_TRUTH_ALLOWED_RELATION_TYPES))
            row_errors.append(
                f"unknown relation type `{relation_type}`; allowed: {allowed}"
            )

        confidence = str(entry.get("confidence") or "").strip().lower()
        if confidence and confidence not in GROUND_TRUTH_ALLOWED_CONFIDENCE:
            allowed = ", ".join(sorted(GROUND_TRUTH_ALLOWED_CONFIDENCE))
            row_errors.append(f"invalid confidence `{confidence}`; allowed: {allowed}")

        reviewed_at = str(entry.get("reviewed_at") or "").strip()
        if reviewed_at:
            try:
                date.fromisoformat(reviewed_at)
            except ValueError:
                row_errors.append(
                    f"invalid `reviewed_at` date `{reviewed_at}`; use YYYY-MM-DD"
                )

        if row_errors:
            errors.extend(f"{row_label}: {message}" for message in row_errors)
            continue

        typed_edge = (source, target, relation_type)
        if typed_edge in seen_typed_edges:
            errors.append(
                f"{row_label}: duplicate curated edge `{source} -> {target}` with relation type `{relation_type}`"
            )
            continue
        seen_typed_edges.add(typed_edge)

        pair = (source, target)
        previous_relation_type = relation_types_by_pair.get(pair)
        if previous_relation_type and previous_relation_type != relation_type:
            errors.append(
                f"{row_label}: conflicting relation types for `{source} -> {target}` "
                f"(`{previous_relation_type}` and `{relation_type}`)"
            )
            continue
        relation_types_by_pair[pair] = relation_type

    return errors


def _load_csv_rows(
    csv_path: Path,
    *,
    columns: Sequence[str],
) -> List[Dict[str, str]]:
    if not csv_path.exists():
        return []

    lines = [
        line
        for line in csv_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not lines:
        return []

    delimiter = "\t" if "\t" in lines[0] else ","
    reader = csv.DictReader(
        io.StringIO("\n".join(lines)), skipinitialspace=True, delimiter=delimiter
    )
    if reader.fieldnames is None:
        return []
    reader.fieldnames = [str(field or "").strip() for field in reader.fieldnames]

    entries: List[Dict[str, str]] = []
    for row in reader:
        normalized = {
            str(key).strip(): str(value).strip()
            for key, value in row.items()
            if key is not None and value is not None
        }
        entries.append(
            {
                **{column: normalized.get(column, "") for column in columns},
                "__line__": reader.line_num,
            }
        )

    return entries


def export_ground_truth_workbook(ecosystem_slug: str | None) -> Path:
    if not ecosystem_slug:
        raise ValueError("Missing ecosystem slug")

    workbook_path = ground_truth_workbook_path(ecosystem_slug)
    workbook_path.parent.mkdir(parents=True, exist_ok=True)

    workbook_xml = ET.Element(
        f"{{{_XLSX_MAIN_NS}}}workbook",
        {
            "xmlns": _XLSX_MAIN_NS,
            "xmlns:r": _XLSX_REL_NS,
        },
    )
    sheets_element = ET.SubElement(workbook_xml, f"{{{_XLSX_MAIN_NS}}}sheets")
    workbook_rels = ET.Element(
        f"{{{_XLSX_PKG_REL_NS}}}Relationships",
        {"xmlns": _XLSX_PKG_REL_NS},
    )

    sheet_xml_by_path: dict[str, bytes] = {}
    for index, (sheet_name, columns) in enumerate(GROUND_TRUTH_WORKBOOK_SHEETS, start=1):
        csv_path = _ground_truth_csv_path(ecosystem_slug, sheet_name)
        rows = _load_csv_rows(csv_path, columns=columns)
        ET.SubElement(
            sheets_element,
            f"{{{_XLSX_MAIN_NS}}}sheet",
            {
                "name": sheet_name,
                "sheetId": str(index),
                f"{{{_XLSX_REL_NS}}}id": f"rId{index}",
            },
        )
        ET.SubElement(
            workbook_rels,
            f"{{{_XLSX_PKG_REL_NS}}}Relationship",
            {
                "Id": f"rId{index}",
                "Type": f"{_XLSX_REL_NS}/worksheet",
                "Target": f"worksheets/sheet{index}.xml",
            },
        )
        sheet_xml_by_path[f"xl/worksheets/sheet{index}.xml"] = _build_sheet_xml(
            columns,
            rows,
        )

    content_types = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>
"""
    package_rels = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{_XLSX_PKG_REL_NS}">
  <Relationship Id="rId1" Type="{_XLSX_REL_NS}/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
"""

    with zipfile.ZipFile(
        workbook_path, "w", compression=zipfile.ZIP_DEFLATED
    ) as workbook:
        workbook.writestr("[Content_Types].xml", content_types)
        workbook.writestr("_rels/.rels", package_rels)
        workbook.writestr(
            "xl/workbook.xml",
            ET.tostring(workbook_xml, encoding="utf-8", xml_declaration=True),
        )
        workbook.writestr(
            "xl/_rels/workbook.xml.rels",
            ET.tostring(workbook_rels, encoding="utf-8", xml_declaration=True),
        )
        for path, sheet_xml in sheet_xml_by_path.items():
            workbook.writestr(path, sheet_xml)

    return workbook_path


def _normalize_iso_date(text: Any) -> str | None:
    value = str(text or "").strip()
    if not value:
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        return None
    return value


def reviewed_ip_policy_for_ecosystem(
    ecosystem_slug: str | None,
) -> Dict[str, Any] | None:
    if not ecosystem_slug:
        return None
    policy = GROUND_TRUTH_REVIEW_POLICIES.get(str(ecosystem_slug))
    return dict(policy) if isinstance(policy, Mapping) else None


def validate_reviewed_ip_policy(
    entries: Sequence[Mapping[str, Any]],
    *,
    ecosystem_slug: str | None,
) -> List[str]:
    policy = reviewed_ip_policy_for_ecosystem(ecosystem_slug)
    if not policy:
        return []

    warnings: List[str] = []
    allowed_source_slugs = {
        str(value).strip()
        for value in policy.get("allowed_source_slugs", ())
        if str(value).strip()
    }
    required_type = str(policy.get("required_type") or "").strip()

    source_scope_violations: List[str] = []
    type_scope_violations: List[str] = []
    type_unknown: List[str] = []

    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        ip = str(entry.get("ip") or "").strip()
        if not ip or ":" not in ip:
            continue
        source_slug, _proposal_id = ip.split(":", 1)
        proposal_type = str(entry.get("type") or "").strip()

        if allowed_source_slugs and source_slug not in allowed_source_slugs:
            source_scope_violations.append(ip)
            continue

        if required_type:
            if not proposal_type:
                type_unknown.append(ip)
            elif proposal_type != required_type:
                type_scope_violations.append(f"{ip} ({proposal_type})")

    if source_scope_violations:
        expected = ", ".join(sorted(allowed_source_slugs))
        examples = ", ".join(source_scope_violations[:5])
        more = (
            ""
            if len(source_scope_violations) <= 5
            else f", +{len(source_scope_violations) - 5} more"
        )
        warnings.append(
            f"reviewed IP scope for `{ecosystem_slug}` currently expects source `{expected}`, "
            f"but {len(source_scope_violations)} row(s) use other source slugs: {examples}{more}"
        )

    if type_scope_violations:
        examples = ", ".join(type_scope_violations[:5])
        more = (
            ""
            if len(type_scope_violations) <= 5
            else f", +{len(type_scope_violations) - 5} more"
        )
        warnings.append(
            f"reviewed IP scope for `{ecosystem_slug}` currently expects proposal type `{required_type}`, "
            f"but {len(type_scope_violations)} row(s) use another type: {examples}{more}"
        )

    if type_unknown:
        examples = ", ".join(type_unknown[:5])
        more = "" if len(type_unknown) <= 5 else f", +{len(type_unknown) - 5} more"
        warnings.append(
            f"reviewed IP scope for `{ecosystem_slug}` expects proposal type metadata, "
            f"but {len(type_unknown)} row(s) have an empty `type`: {examples}{more}"
        )

    return warnings


def validate_reviewed_ip_entries(
    entries: Sequence[Mapping[str, Any]],
    *,
    source_configs_by_slug: Mapping[str, Mapping[str, Any]],
) -> List[str]:
    errors: List[str] = []
    seen_ips: set[str] = set()

    for index, entry in enumerate(entries):
        row_label = (
            f"row {entry.get('__line__')}"
            if isinstance(entry, Mapping) and entry.get("__line__")
            else f"row {index + 2}"
        )
        if not isinstance(entry, Mapping):
            errors.append(f"{row_label}: entry must be an object")
            continue

        row_errors: List[str] = []
        raw_ip = str(entry.get("ip") or "").strip()
        normalized_ip = None
        try:
            source_slug, proposal_id = _validate_ground_truth_graph_key(
                raw_ip,
                field_name="ip",
                source_configs_by_slug=source_configs_by_slug,
            )
            normalized_ip = f"{source_slug}:{proposal_id}"
        except ValueError as exc:
            row_errors.append(str(exc))

        reviewed_at = str(entry.get("reviewed_at") or "").strip()
        if reviewed_at:
            try:
                date.fromisoformat(reviewed_at)
            except ValueError:
                row_errors.append(
                    f"invalid `reviewed_at` date `{reviewed_at}`; use YYYY-MM-DD"
                )

        extracted_target_count = str(entry.get("extracted_target_count") or "").strip()
        if extracted_target_count:
            try:
                if int(extracted_target_count) < 0:
                    raise ValueError
            except ValueError:
                row_errors.append(
                    "`extracted_target_count` must be a non-negative integer"
                )

        sampling_strategy = str(entry.get("sampling_strategy") or "").strip()
        if (
            sampling_strategy
            and sampling_strategy not in REVIEWED_IP_ALLOWED_SAMPLING_STRATEGIES
        ):
            allowed = ", ".join(sorted(REVIEWED_IP_ALLOWED_SAMPLING_STRATEGIES))
            row_errors.append(
                f"invalid `sampling_strategy` `{sampling_strategy}`; allowed: {allowed}"
            )

        density_bucket = str(entry.get("density_bucket") or "").strip()
        if (
            density_bucket
            and density_bucket != "-"
            and density_bucket not in REVIEWED_IP_ALLOWED_DENSITY_BUCKETS
        ):
            allowed = ", ".join(sorted(REVIEWED_IP_ALLOWED_DENSITY_BUCKETS))
            row_errors.append(
                f"invalid `density_bucket` `{density_bucket}`; allowed: {allowed}"
            )

        density_basis = str(entry.get("density_basis") or "").strip()
        if (
            density_basis
            and density_basis != "-"
            and density_basis not in REVIEWED_IP_ALLOWED_DENSITY_BASIS
        ):
            allowed = ", ".join(sorted(REVIEWED_IP_ALLOWED_DENSITY_BASIS))
            row_errors.append(
                f"invalid `density_basis` `{density_basis}`; allowed: {allowed}"
            )

        created = str(entry.get("created") or "").strip()
        if created:
            try:
                date.fromisoformat(created)
            except ValueError:
                row_errors.append(f"invalid `created` date `{created}`; use YYYY-MM-DD")

        if row_errors:
            errors.extend(f"{row_label}: {message}" for message in row_errors)
            continue

        if normalized_ip in seen_ips:
            errors.append(f"{row_label}: duplicate reviewed IP `{normalized_ip}`")
            continue
        seen_ips.add(str(normalized_ip))

    return errors


def load_ground_truth_curated_entries(
    ecosystem_slug: str | None, *, strict: bool = True
) -> List[Dict[str, str]]:
    if not ecosystem_slug:
        return []

    sync_ground_truth_csvs_from_workbook(ecosystem_slug)
    csv_path = (
        Path("ip_data") / str(ecosystem_slug) / "ground_truth" / "interrelations.csv"
    )
    entries = [
        entry
        for entry in _load_csv_rows(csv_path, columns=GROUND_TRUTH_CSV_COLUMNS)
        if entry.get("source") and entry.get("target")
    ]

    if strict:
        errors = validate_ground_truth_curated_entries(
            entries,
            source_configs_by_slug=ground_truth_source_configs_by_slug(ecosystem_slug),
        )
        if errors:
            raise ValueError(
                f"Ground-truth validation failed for `{csv_path}`:\n- "
                + "\n- ".join(errors)
            )

    return entries


def load_ground_truth_ips(
    ecosystem_slug: str | None, *, strict: bool = True
) -> List[Dict[str, str]]:
    if not ecosystem_slug:
        return []

    sync_ground_truth_csvs_from_workbook(ecosystem_slug)
    csv_path = Path("ip_data") / str(ecosystem_slug) / "ground_truth" / "ips.csv"
    entries = [
        entry
        for entry in _load_csv_rows(csv_path, columns=REVIEWED_IPS_CSV_COLUMNS)
        if entry.get("ip")
    ]

    if strict:
        errors = validate_reviewed_ip_entries(
            entries,
            source_configs_by_slug=ground_truth_source_configs_by_slug(ecosystem_slug),
        )
        if errors:
            raise ValueError(
                f"Reviewed-IP validation failed for `{csv_path}`:\n- "
                + "\n- ".join(errors)
            )

    return entries


def completed_reviewed_ip_entries(
    entries: Sequence[Mapping[str, Any]],
) -> List[Dict[str, str]]:
    completed: List[Dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        reviewed_at = _normalize_iso_date(entry.get("reviewed_at"))
        if not reviewed_at:
            continue
        completed.append(
            {
                str(key): str(value)
                for key, value in entry.items()
                if key is not None and value is not None
            }
        )
    return completed
