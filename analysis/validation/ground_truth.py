from __future__ import annotations

import csv
import io
import re
import zipfile
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from analysis.dependencies.constants import INTERRELATION_TYPES
from analysis.reference_ids import normalize_reference_id_for_config

GROUND_TRUTH_WORKBOOK_FILENAME = "ground_truth.xlsx"
REVIEWED_IP_APPEND_WORKBOOK_FILENAME = "ips_append.xlsx"


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
GROUND_TRUTH_ALLOWED_RELATION_TYPES = INTERRELATION_TYPES
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
        # Reviewed IPs may come from any source listed here; `required_type`
        # is enforced per source when set. BIPs intentionally sample across
        # all proposal types (Specification/Informational/Process) to match
        # catalog-wide ratios, so no type restriction applies here.
        "source_policies": {
            "bips": {},
            "slips": {},
        },
    },
}
WORKBOOK_IPS_COLUMNS = (
    "ip_source",
    "ip_id",
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
WORKBOOK_INTERRELATIONS_COLUMNS = (
    "source",
    "source_id",
    "target",
    "target_id",
    "relation_type",
    "confidence",
    "evidence",
    "note",
    "reviewer",
    "reviewed_at",
)
GROUND_TRUTH_WORKBOOK_SHEETS = (
    ("ips", WORKBOOK_IPS_COLUMNS),
    ("interrelations", WORKBOOK_INTERRELATIONS_COLUMNS),
)
_XLSX_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_XLSX_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_XLSX_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_XLSX_REL_NS_STRICT = "http://purl.oclc.org/ooxml/officeDocument/relationships"


def ground_truth_directory(ecosystem_slug: str | None) -> Path:
    return Path("ip_data") / str(ecosystem_slug) / "ground_truth"


def ground_truth_workbook_path(ecosystem_slug: str | None) -> Path:
    return ground_truth_directory(ecosystem_slug) / GROUND_TRUTH_WORKBOOK_FILENAME


def reviewed_ip_append_workbook_path(ecosystem_slug: str | None) -> Path:
    return ground_truth_directory(ecosystem_slug) / REVIEWED_IP_APPEND_WORKBOOK_FILENAME


def _ground_truth_csv_path(ecosystem_slug: str | None, sheet_name: str) -> Path:
    if sheet_name == "ips":
        filename = "ips.csv"
    elif sheet_name == "interrelations":
        filename = "interrelations.csv"
    else:
        raise ValueError(f"Unknown ground-truth sheet `{sheet_name}`")
    return ground_truth_directory(ecosystem_slug) / filename


def _split_graph_key(value: Any) -> tuple[str, str]:
    text = str(value or "").strip()
    if ":" not in text:
        return "", text
    source_slug, proposal_id = text.split(":", 1)
    return source_slug.strip(), proposal_id.strip()


def _compose_graph_key(source_slug: Any, proposal_id: Any) -> str:
    source_text = str(source_slug or "").strip()
    proposal_text = str(proposal_id or "").strip()
    if not source_text and not proposal_text:
        return ""
    if not source_text or not proposal_text:
        return ""
    return f"{source_text}:{proposal_text}"


def _element_local_name(element: ET.Element) -> str:
    return str(element.tag).split("}", 1)[-1]


def _element_namespace(element: ET.Element) -> str:
    tag = str(element.tag)
    if tag.startswith("{") and "}" in tag:
        return tag[1:].split("}", 1)[0]
    return _XLSX_MAIN_NS


def _child_elements(parent: ET.Element, local_name: str) -> list[ET.Element]:
    return [child for child in list(parent) if _element_local_name(child) == local_name]


def _first_child(parent: ET.Element, local_name: str) -> ET.Element | None:
    for child in list(parent):
        if _element_local_name(child) == local_name:
            return child
    return None


def _find_descendants(root: ET.Element, local_name: str) -> list[ET.Element]:
    return [
        element for element in root.iter() if _element_local_name(element) == local_name
    ]


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
    style_index: str | None = None,
    namespace: str | None = None,
) -> None:
    if value == "":
        return
    sheet_namespace = namespace or _element_namespace(row_element)
    attributes = {
        "r": f"{_excel_column_name(column_index)}{row_number}",
        "t": "inlineStr",
    }
    if style_index:
        attributes["s"] = style_index
    cell = ET.SubElement(row_element, f"{{{sheet_namespace}}}c", attributes)
    inline_string = ET.SubElement(cell, f"{{{sheet_namespace}}}is")
    text = ET.SubElement(inline_string, f"{{{sheet_namespace}}}t")
    if value[:1].isspace() or value[-1:].isspace():
        text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    text.text = value


def _build_sheet_xml(
    columns: Sequence[str], rows: Sequence[Mapping[str, Any]]
) -> bytes:
    worksheet_namespace = _XLSX_MAIN_NS
    worksheet = ET.Element(
        f"{{{worksheet_namespace}}}worksheet",
        {"xmlns": worksheet_namespace},
    )
    sheet_data = ET.SubElement(worksheet, f"{{{worksheet_namespace}}}sheetData")

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
            namespace=worksheet_namespace,
        )

    for row_number, row in enumerate(rows, start=2):
        row_element = ET.SubElement(
            sheet_data,
            f"{{{worksheet_namespace}}}row",
            {"r": str(row_number)},
        )
        for index, column in enumerate(columns):
            _append_inline_string_cell(
                row_element,
                row_number=row_number,
                column_index=index,
                value=str(row.get(column, "") or ""),
                namespace=worksheet_namespace,
            )

    return ET.tostring(worksheet, encoding="utf-8", xml_declaration=True)


def _write_xlsx_workbook(
    workbook_path: Path,
    *,
    sheets: Sequence[tuple[str, Sequence[str], Sequence[Mapping[str, Any]]]],
) -> Path:
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

    content_type_lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '  <Default Extension="xml" ContentType="application/xml"/>',
        '  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
    ]

    for index, (sheet_name, columns, rows) in enumerate(sheets, start=1):
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
            columns, rows
        )
        content_type_lines.append(
            f'  <Override PartName="/xl/worksheets/sheet{index}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )

    content_type_lines.append("</Types>")
    content_types = "\n".join(content_type_lines) + "\n"
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
        value_element = _first_child(cell, "v")
        raw_index = (
            str(value_element.text or "").strip() if value_element is not None else ""
        )
        if raw_index.isdigit():
            index = int(raw_index)
            if 0 <= index < len(shared_strings):
                return shared_strings[index].strip()
        return ""

    value_element = _first_child(cell, "v")
    value = str(value_element.text or "").strip() if value_element is not None else ""
    if value and column_name in {"created", "reviewed_at"}:
        try:
            serial = float(value)
        except ValueError:
            return value
        if serial >= 1 and serial.is_integer():
            base = date(1899, 12, 30)
            return base.fromordinal(base.toordinal() + int(serial)).isoformat()
    return value


def _load_shared_strings(workbook: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for string_item in _find_descendants(root, "si"):
        values.append("".join(string_item.itertext()))
    return values


def _sheet_path_by_name(workbook: zipfile.ZipFile, sheet_name: str) -> str:
    workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
    rels_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    targets_by_rel_id = {
        rel.get("Id"): rel.get("Target")
        for rel in _find_descendants(rels_root, "Relationship")
    }
    for sheet in _find_descendants(workbook_root, "sheet"):
        if str(sheet.get("name") or "").strip() != sheet_name:
            continue
        rel_id = (
            sheet.get(f"{{{_XLSX_REL_NS}}}id")
            or sheet.get(f"{{{_XLSX_REL_NS_STRICT}}}id")
            or sheet.get("id")
        )
        target = targets_by_rel_id.get(rel_id)
        if target:
            return f"xl/{target.lstrip('/')}"
    raise ValueError(f"Ground-truth workbook is missing sheet `{sheet_name}`")


def _load_xlsx_sheet_entries(
    workbook_path: Path,
    *,
    sheet_name: str,
    columns: Sequence[str],
) -> list[dict[str, str]]:
    with zipfile.ZipFile(workbook_path) as workbook:
        shared_strings = _load_shared_strings(workbook)
        sheet_path = _sheet_path_by_name(workbook, sheet_name)
        sheet_root = ET.fromstring(workbook.read(sheet_path))

    rows: list[list[str]] = []
    for row_element in _find_descendants(sheet_root, "row"):
        values_by_index: dict[int, str] = {}
        for cell in _child_elements(row_element, "c"):
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
    if sheet_name == "ips":
        has_split = "ip_source" in header_index and "ip_id" in header_index
        has_legacy = "ip" in header_index
        if not has_split and not has_legacy:
            raise ValueError(
                "Ground-truth workbook sheet `ips` must provide either `ip` "
                "or both `ip_source` and `ip_id`"
            )
    elif sheet_name == "interrelations":
        has_split = all(
            key in header_index
            for key in ("source", "source_id", "target", "target_id")
        )
        has_legacy = "source" in header_index and "target" in header_index
        if not has_split and not has_legacy:
            raise ValueError(
                "Ground-truth workbook sheet `interrelations` must provide either "
                "legacy `source`/`target` graph-key columns or split source/id columns"
            )
    else:
        missing = [column for column in columns if column not in header_index]
        if missing:
            raise ValueError(
                f"Ground-truth workbook sheet `{sheet_name}` is missing columns: {', '.join(missing)}"
            )

    entries: list[dict[str, str]] = []
    for row_values in rows[1:]:
        entry = {
            column: str(row_values[index]).strip() if index < len(row_values) else ""
            for column, index in header_index.items()
        }
        if any(entry.values()):
            entries.append(entry)
    return entries


def _load_ground_truth_rows_from_workbook(
    ecosystem_slug: str | None,
    *,
    sheet_name: str,
) -> list[dict[str, str]]:
    workbook_path = ground_truth_workbook_path(ecosystem_slug)
    if not workbook_path.exists():
        return []
    workbook_columns_by_sheet = dict(GROUND_TRUTH_WORKBOOK_SHEETS)
    rows = _load_xlsx_sheet_entries(
        workbook_path,
        sheet_name=sheet_name,
        columns=workbook_columns_by_sheet[sheet_name],
    )
    return _workbook_rows_to_csv_rows(sheet_name, rows)


def _workbook_rows_to_csv_rows(
    sheet_name: str,
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    if sheet_name == "ips":
        normalized_rows: list[dict[str, str]] = []
        for row in rows:
            graph_key = str(row.get("ip") or "").strip()
            if not graph_key:
                graph_key = _compose_graph_key(row.get("ip_source"), row.get("ip_id"))
            source_slug, proposal_id = _split_graph_key(graph_key)
            normalized_rows.append(
                {
                    "ip": _compose_graph_key(source_slug, proposal_id),
                    "reviewer": str(row.get("reviewer") or "").strip(),
                    "reviewed_at": str(row.get("reviewed_at") or "").strip(),
                    "sampling_strategy": str(
                        row.get("sampling_strategy") or ""
                    ).strip(),
                    "sampling_snapshot": str(
                        row.get("sampling_snapshot") or ""
                    ).strip(),
                    "sampling_seed": str(row.get("sampling_seed") or "").strip(),
                    "era_bucket": str(row.get("era_bucket") or "").strip(),
                    "density_bucket": str(row.get("density_bucket") or "").strip(),
                    "density_basis": str(row.get("density_basis") or "").strip(),
                    "created": str(row.get("created") or "").strip(),
                    "status": str(row.get("status") or "").strip(),
                    "type": str(row.get("type") or "").strip(),
                    "layer": str(row.get("layer") or "").strip(),
                    "title": str(row.get("title") or "").strip(),
                    "extracted_target_count": str(
                        row.get("extracted_target_count") or ""
                    ).strip(),
                    "note": str(row.get("note") or "").strip(),
                }
            )
        return normalized_rows

    if sheet_name == "interrelations":
        normalized_rows = []
        for row in rows:
            source_key = str(
                row.get("source_graph_key") or row.get("source") or ""
            ).strip()
            target_key = str(
                row.get("target_graph_key") or row.get("target") or ""
            ).strip()
            if ":" not in source_key:
                source_key = _compose_graph_key(row.get("source"), row.get("source_id"))
            if ":" not in target_key:
                target_key = _compose_graph_key(row.get("target"), row.get("target_id"))
            normalized_rows.append(
                {
                    "source": source_key,
                    "target": target_key,
                    "relation_type": str(row.get("relation_type") or "").strip(),
                    "confidence": str(row.get("confidence") or "").strip(),
                    "evidence": str(row.get("evidence") or "").strip(),
                    "note": str(row.get("note") or "").strip(),
                    "reviewer": str(row.get("reviewer") or "").strip(),
                    "reviewed_at": str(row.get("reviewed_at") or "").strip(),
                }
            )
        return normalized_rows

    raise ValueError(f"Unknown ground-truth sheet `{sheet_name}`")


def _csv_rows_to_workbook_rows(
    sheet_name: str,
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    if sheet_name == "ips":
        workbook_rows: list[dict[str, str]] = []
        for row in rows:
            source_slug, proposal_id = _split_graph_key(row.get("ip"))
            workbook_rows.append(
                {
                    "ip_source": source_slug,
                    "ip_id": proposal_id,
                    "reviewer": str(row.get("reviewer") or "").strip(),
                    "reviewed_at": str(row.get("reviewed_at") or "").strip(),
                    "sampling_strategy": str(
                        row.get("sampling_strategy") or ""
                    ).strip(),
                    "sampling_snapshot": str(
                        row.get("sampling_snapshot") or ""
                    ).strip(),
                    "sampling_seed": str(row.get("sampling_seed") or "").strip(),
                    "era_bucket": str(row.get("era_bucket") or "").strip(),
                    "density_bucket": str(row.get("density_bucket") or "").strip(),
                    "density_basis": str(row.get("density_basis") or "").strip(),
                    "created": str(row.get("created") or "").strip(),
                    "status": str(row.get("status") or "").strip(),
                    "type": str(row.get("type") or "").strip(),
                    "layer": str(row.get("layer") or "").strip(),
                    "title": str(row.get("title") or "").strip(),
                    "extracted_target_count": str(
                        row.get("extracted_target_count") or ""
                    ).strip(),
                    "note": str(row.get("note") or "").strip(),
                }
            )
        return workbook_rows

    if sheet_name == "interrelations":
        workbook_rows = []
        for row in rows:
            source_slug, source_id = _split_graph_key(row.get("source"))
            target_slug, target_id = _split_graph_key(row.get("target"))
            workbook_rows.append(
                {
                    "source": source_slug,
                    "source_id": source_id,
                    "target": target_slug,
                    "target_id": target_id,
                    "relation_type": str(row.get("relation_type") or "").strip(),
                    "confidence": str(row.get("confidence") or "").strip(),
                    "evidence": str(row.get("evidence") or "").strip(),
                    "note": str(row.get("note") or "").strip(),
                    "reviewer": str(row.get("reviewer") or "").strip(),
                    "reviewed_at": str(row.get("reviewed_at") or "").strip(),
                }
            )
        return workbook_rows

    raise ValueError(f"Unknown ground-truth sheet `{sheet_name}`")


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

    csv_columns_by_sheet = {
        "ips": REVIEWED_IPS_CSV_COLUMNS,
        "interrelations": GROUND_TRUTH_CSV_COLUMNS,
    }

    for sheet_name, workbook_columns in GROUND_TRUTH_WORKBOOK_SHEETS:
        rows = _load_xlsx_sheet_entries(
            workbook_path,
            sheet_name=sheet_name,
            columns=workbook_columns,
        )
        csv_rows = _workbook_rows_to_csv_rows(sheet_name, rows)
        _write_csv_rows(
            _ground_truth_csv_path(ecosystem_slug, sheet_name),
            columns=csv_columns_by_sheet[sheet_name],
            rows=csv_rows,
        )
    return True


def load_reviewed_ip_append_rows(ecosystem_slug: str | None) -> list[dict[str, str]]:
    if not ecosystem_slug:
        return []
    workbook_path = reviewed_ip_append_workbook_path(ecosystem_slug)
    if not workbook_path.exists():
        return []
    return [
        entry
        for entry in _load_xlsx_sheet_entries(
            workbook_path,
            sheet_name="ips",
            columns=WORKBOOK_IPS_COLUMNS,
        )
        if any(str(value or "").strip() for value in entry.values())
    ]


def write_reviewed_ip_append_workbook(
    ecosystem_slug: str | None,
    rows: Sequence[Mapping[str, Any]],
) -> Path:
    if not ecosystem_slug:
        raise ValueError("Missing ecosystem slug")

    workbook_path = reviewed_ip_append_workbook_path(ecosystem_slug)
    workbook_rows = _csv_rows_to_workbook_rows("ips", rows)
    return _write_xlsx_workbook(
        workbook_path,
        sheets=(("ips", WORKBOOK_IPS_COLUMNS, workbook_rows),),
    )


def ground_truth_source_configs_by_slug(
    ecosystem_slug: str | None,
) -> dict[str, dict[str, Any]]:
    if not ecosystem_slug:
        return {}

    from ecosystems import ECOSYSTEM_REGISTRY

    ecosystem = ECOSYSTEM_REGISTRY.get(str(ecosystem_slug), {})
    sources = ecosystem.get("sources", {}) if isinstance(ecosystem, Mapping) else {}
    configs: dict[str, dict[str, Any]] = {}
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
) -> list[str]:
    errors: list[str] = []
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

        row_errors: list[str] = []
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
        reviewer = str(entry.get("reviewer") or "").strip()
        relation_type = str(entry.get("relation_type") or "").strip().lower()
        if not relation_type:
            row_errors.append("missing `relation_type`")
        elif relation_type not in GROUND_TRUTH_ALLOWED_RELATION_TYPES:
            allowed = ", ".join(sorted(GROUND_TRUTH_ALLOWED_RELATION_TYPES))
            row_errors.append(
                f"unknown relation type `{relation_type}`; allowed: {allowed}"
            )

        if not reviewer:
            row_errors.append("missing `reviewer`")

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
) -> list[dict[str, str]]:
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

    entries: list[dict[str, str]] = []
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
    csv_columns_by_sheet = {
        "ips": REVIEWED_IPS_CSV_COLUMNS,
        "interrelations": GROUND_TRUTH_CSV_COLUMNS,
    }

    for index, (sheet_name, workbook_columns) in enumerate(
        GROUND_TRUTH_WORKBOOK_SHEETS, start=1
    ):
        csv_path = _ground_truth_csv_path(ecosystem_slug, sheet_name)
        rows = _load_csv_rows(csv_path, columns=csv_columns_by_sheet[sheet_name])
        workbook_rows = _csv_rows_to_workbook_rows(sheet_name, rows)
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
            workbook_columns,
            workbook_rows,
        )

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
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
) -> dict[str, Any] | None:
    if not ecosystem_slug:
        return None
    policy = GROUND_TRUTH_REVIEW_POLICIES.get(str(ecosystem_slug))
    return dict(policy) if isinstance(policy, Mapping) else None


def reviewed_ip_source_policies(
    policy: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    if not isinstance(policy, Mapping):
        return {}
    raw = policy.get("source_policies")
    if not isinstance(raw, Mapping):
        return {}
    return {
        str(slug).strip(): (
            dict(source_policy) if isinstance(source_policy, Mapping) else {}
        )
        for slug, source_policy in raw.items()
        if str(slug).strip()
    }


def validate_reviewed_ip_policy(
    entries: Sequence[Mapping[str, Any]],
    *,
    ecosystem_slug: str | None,
) -> list[str]:
    policy = reviewed_ip_policy_for_ecosystem(ecosystem_slug)
    if not policy:
        return []

    warnings: list[str] = []
    source_policies = reviewed_ip_source_policies(policy)

    source_scope_violations: list[str] = []
    type_scope_violations: dict[str, list[str]] = {}
    type_unknown: dict[str, list[str]] = {}

    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        ip = str(entry.get("ip") or "").strip()
        if not ip or ":" not in ip:
            continue
        source_slug, _proposal_id = ip.split(":", 1)
        proposal_type = str(entry.get("type") or "").strip()

        if source_policies and source_slug not in source_policies:
            source_scope_violations.append(ip)
            continue

        required_type = str(
            source_policies.get(source_slug, {}).get("required_type") or ""
        ).strip()
        if required_type:
            if not proposal_type:
                type_unknown.setdefault(source_slug, []).append(ip)
            elif proposal_type != required_type:
                type_scope_violations.setdefault(source_slug, []).append(
                    f"{ip} ({proposal_type})"
                )

    if source_scope_violations:
        expected = ", ".join(sorted(source_policies))
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

    for source_slug, violations in sorted(type_scope_violations.items()):
        required_type = str(
            source_policies.get(source_slug, {}).get("required_type") or ""
        ).strip()
        examples = ", ".join(violations[:5])
        more = "" if len(violations) <= 5 else f", +{len(violations) - 5} more"
        warnings.append(
            f"reviewed IP scope for `{ecosystem_slug}` currently expects proposal type `{required_type}` "
            f"for source `{source_slug}`, but {len(violations)} row(s) use another type: {examples}{more}"
        )

    for source_slug, unknown in sorted(type_unknown.items()):
        examples = ", ".join(unknown[:5])
        more = "" if len(unknown) <= 5 else f", +{len(unknown) - 5} more"
        warnings.append(
            f"reviewed IP scope for `{ecosystem_slug}` expects proposal type metadata "
            f"for source `{source_slug}`, but {len(unknown)} row(s) have an empty `type`: {examples}{more}"
        )

    return warnings


def validate_reviewed_ip_entries(
    entries: Sequence[Mapping[str, Any]],
    *,
    source_configs_by_slug: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    errors: list[str] = []
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

        row_errors: list[str] = []
        raw_ip = str(entry.get("ip") or "").strip()
        reviewer = str(entry.get("reviewer") or "").strip()
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

        if not reviewer:
            row_errors.append("missing `reviewer`")

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
) -> list[dict[str, str]]:
    if not ecosystem_slug:
        return []

    workbook_path = ground_truth_workbook_path(ecosystem_slug)
    csv_path = _ground_truth_csv_path(ecosystem_slug, "interrelations")
    if workbook_path.exists():
        entries = [
            entry
            for entry in _load_ground_truth_rows_from_workbook(
                ecosystem_slug, sheet_name="interrelations"
            )
            if entry.get("source") and entry.get("target")
        ]
    else:
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
            source_path = workbook_path if workbook_path.exists() else csv_path
            raise ValueError(
                f"Ground-truth validation failed for `{source_path}`:\n- "
                + "\n- ".join(errors)
            )

    return entries


def load_ground_truth_ips(
    ecosystem_slug: str | None, *, strict: bool = True
) -> list[dict[str, str]]:
    if not ecosystem_slug:
        return []

    workbook_path = ground_truth_workbook_path(ecosystem_slug)
    csv_path = _ground_truth_csv_path(ecosystem_slug, "ips")
    if workbook_path.exists():
        entries = [
            entry
            for entry in _load_ground_truth_rows_from_workbook(
                ecosystem_slug, sheet_name="ips"
            )
            if entry.get("ip")
        ]
    else:
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
            source_path = workbook_path if workbook_path.exists() else csv_path
            raise ValueError(
                f"Reviewed-IP validation failed for `{source_path}`:\n- "
                + "\n- ".join(errors)
            )

    return entries


def completed_reviewed_ip_entries(
    entries: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    completed: list[dict[str, str]] = []
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
