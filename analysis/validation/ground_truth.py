from __future__ import annotations

import csv
import io
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence


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
GROUND_TRUTH_ALLOWED_RELATION_TYPES = {"depends_on", "supersedes", "superseded_by", "references"}
GROUND_TRUTH_ALLOWED_CONFIDENCE = {"low", "medium", "high"}
REVIEWED_IP_ALLOWED_SAMPLING_STRATEGIES = {"sampler", "manual"}
REVIEWED_IP_ALLOWED_DENSITY_BUCKETS = {"none", "low", "high"}
REVIEWED_IP_ALLOWED_DENSITY_BASIS = {"all_methods", "regex_only", "llm_only", "preamble_only"}
GROUND_TRUTH_GRAPH_KEY_RE = re.compile(r"^(?P<source>[A-Za-z0-9_-]+):(?P<id>[^:\s]+)$")
HEX_REFERENCE_CLASS_PATTERN = re.compile(r"\[[^\]]*0-9[^\]]*A-F[^\]]*a-f[^\]]*\]")


def _uses_hex_proposal_ids(proposal_label: str = "IP", reference_pattern: str = "") -> bool:
    return proposal_label.upper() == "NIP" or bool(HEX_REFERENCE_CLASS_PATTERN.search(reference_pattern))


def _normalize_reference_id_for_config(
    value: Any,
    config: Mapping[str, Any],
    *,
    max_reference_digits: int = 6,
) -> str | None:
    text = str(value).strip()
    if not text:
        return None

    proposal_label = str(config.get("proposal_label") or "IP")
    reference_pattern = str(config.get("reference_pattern") or "")
    max_proposal_id = config.get("max_proposal_id")

    if _uses_hex_proposal_ids(proposal_label, reference_pattern):
        if not re.fullmatch(rf"[0-9A-Fa-f]{{1,{max_reference_digits}}}", text):
            return None
        number = int(text, 16)
        if max_proposal_id is not None and number > int(max_proposal_id):
            return None
        normalized = text.upper()
        return normalized.zfill(2) if len(normalized) == 1 else normalized

    try:
        number = int(text)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    if max_proposal_id is not None and number > int(max_proposal_id):
        return None
    return str(number)


def ground_truth_source_configs_by_slug(ecosystem_slug: str | None) -> Dict[str, Dict[str, Any]]:
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
        raise ValueError(f"`{field_name}` uses unknown source slug `{source_slug}`; known sources: {known}")

    normalized = _normalize_reference_id_for_config(proposal_id, source_config)
    if normalized is None:
        raise ValueError(f"`{field_name}` has an invalid proposal id for source `{source_slug}`")

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
        row_label = f"row {entry.get('__line__')}" if isinstance(entry, Mapping) and entry.get("__line__") else f"row {index + 2}"
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
            row_errors.append(f"unknown relation type `{relation_type}`; allowed: {allowed}")

        confidence = str(entry.get("confidence") or "").strip().lower()
        if confidence and confidence not in GROUND_TRUTH_ALLOWED_CONFIDENCE:
            allowed = ", ".join(sorted(GROUND_TRUTH_ALLOWED_CONFIDENCE))
            row_errors.append(f"invalid confidence `{confidence}`; allowed: {allowed}")

        reviewed_at = str(entry.get("reviewed_at") or "").strip()
        if reviewed_at:
            try:
                date.fromisoformat(reviewed_at)
            except ValueError:
                row_errors.append(f"invalid `reviewed_at` date `{reviewed_at}`; use YYYY-MM-DD")

        if row_errors:
            errors.extend(f"{row_label}: {message}" for message in row_errors)
            continue

        typed_edge = (source, target, relation_type)
        if typed_edge in seen_typed_edges:
            errors.append(f"{row_label}: duplicate curated edge `{source} -> {target}` with relation type `{relation_type}`")
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
    reader = csv.DictReader(io.StringIO("\n".join(lines)), skipinitialspace=True, delimiter=delimiter)
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
        entries.append({
            **{column: normalized.get(column, "") for column in columns},
            "__line__": reader.line_num,
        })

    return entries


def _normalize_iso_date(text: Any) -> str | None:
    value = str(text or "").strip()
    if not value:
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        return None
    return value


def validate_reviewed_ip_entries(
    entries: Sequence[Mapping[str, Any]],
    *,
    source_configs_by_slug: Mapping[str, Mapping[str, Any]],
) -> List[str]:
    errors: List[str] = []
    seen_ips: set[str] = set()

    for index, entry in enumerate(entries):
        row_label = f"row {entry.get('__line__')}" if isinstance(entry, Mapping) and entry.get("__line__") else f"row {index + 2}"
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
                row_errors.append(f"invalid `reviewed_at` date `{reviewed_at}`; use YYYY-MM-DD")

        extracted_target_count = str(entry.get("extracted_target_count") or "").strip()
        if extracted_target_count:
            try:
                if int(extracted_target_count) < 0:
                    raise ValueError
            except ValueError:
                row_errors.append("`extracted_target_count` must be a non-negative integer")

        sampling_strategy = str(entry.get("sampling_strategy") or "").strip()
        if sampling_strategy and sampling_strategy not in REVIEWED_IP_ALLOWED_SAMPLING_STRATEGIES:
            allowed = ", ".join(sorted(REVIEWED_IP_ALLOWED_SAMPLING_STRATEGIES))
            row_errors.append(f"invalid `sampling_strategy` `{sampling_strategy}`; allowed: {allowed}")

        density_bucket = str(entry.get("density_bucket") or "").strip()
        if density_bucket and density_bucket != "-" and density_bucket not in REVIEWED_IP_ALLOWED_DENSITY_BUCKETS:
            allowed = ", ".join(sorted(REVIEWED_IP_ALLOWED_DENSITY_BUCKETS))
            row_errors.append(f"invalid `density_bucket` `{density_bucket}`; allowed: {allowed}")

        density_basis = str(entry.get("density_basis") or "").strip()
        if density_basis and density_basis != "-" and density_basis not in REVIEWED_IP_ALLOWED_DENSITY_BASIS:
            allowed = ", ".join(sorted(REVIEWED_IP_ALLOWED_DENSITY_BASIS))
            row_errors.append(f"invalid `density_basis` `{density_basis}`; allowed: {allowed}")

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


def load_ground_truth_curated_entries(ecosystem_slug: str | None, *, strict: bool = True) -> List[Dict[str, str]]:
    if not ecosystem_slug:
        return []

    csv_path = Path("ip_data") / str(ecosystem_slug) / "ground_truth" / "interrelations.csv"
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
                f"Ground-truth validation failed for `{csv_path}`:\n- " + "\n- ".join(errors)
            )

    return entries


def load_ground_truth_ips(ecosystem_slug: str | None, *, strict: bool = True) -> List[Dict[str, str]]:
    if not ecosystem_slug:
        return []

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
                f"Reviewed-IP validation failed for `{csv_path}`:\n- " + "\n- ".join(errors)
            )

    return entries


def completed_reviewed_ip_entries(entries: Sequence[Mapping[str, Any]]) -> List[Dict[str, str]]:
    completed: List[Dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        reviewed_at = _normalize_iso_date(entry.get("reviewed_at"))
        if not reviewed_at:
            continue
        completed.append({str(key): str(value) for key, value in entry.items() if key is not None and value is not None})
    return completed
