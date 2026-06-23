import json
import csv
import io
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from analysis.dependencies.utils import normalize_reference_id_for_config, uses_hex_proposal_ids
from analysis.dependencies.constants import (
    BODY_EXTRACTED_LLM,
    BODY_EXTRACTED_REGEX,
    GROUND_TRUTH_CURATED,
    PREAMBLE_EXTRACTED,
)
from analysis.authorship.mining import get_git_authors_on_first_day
from analysis.proposal_schema import get_formal_compliance, get_interrelations, normalize_proposal_document
from pipeline.source_context import SourceContext
from analysis.utils import parse_date_ymd as _parse_date_ymd

RELATION_REFERENCE = "reference"
RELATION_IMPLICIT_DEPENDENCY = "implicit_dependency"
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
EDGE_BASE_FIELDS = {"source", "target", "extraction_method", "relation_type", "value"}
GROUND_TRUTH_ALLOWED_RELATION_TYPES = {"depends_on", "supersedes", "references"}
GROUND_TRUTH_ALLOWED_CONFIDENCE = {"low", "medium", "high"}
GROUND_TRUTH_GRAPH_KEY_RE = re.compile(r"^(?P<source>[A-Za-z0-9_-]+):(?P<id>[^:\s]+)$")


def build_graph_key(source_slug: str | None, proposal_id: Any) -> str:
    return f"{source_slug}:{proposal_id}" if source_slug else str(proposal_id)


def make_dependency_edge(
    source: Any,
    target: Any,
    extraction_method: str,
    relation_type: str,
    value: Any = 1,
    **extra: Any,
) -> Dict[str, Any]:
    return {
        "source": str(source),
        "target": str(target),
        "extraction_method": extraction_method,
        "relation_type": relation_type,
        "value": value,
        **extra,
    }


def _link_endpoint_to_graph_key(value: Any, source_slug: str | None = None) -> str:
    text = str(value)
    if ":" in text:
        return text
    return build_graph_key(source_slug, text)


def dependency_edges_from_links(links_by_type: Dict[str, Any], source_slug: str | None = None) -> List[Dict[str, Any]]:
    edges: List[Dict[str, Any]] = []
    if not isinstance(links_by_type, dict):
        return edges

    for link_type, links in links_by_type.items():
        if link_type == PREAMBLE_EXTRACTED and isinstance(links, dict):
            for relation_type, subtype_links in links.items():
                for link in subtype_links or []:
                    edges.append(
                        make_dependency_edge(
                            _link_endpoint_to_graph_key(link.get("source"), source_slug),
                            _link_endpoint_to_graph_key(link.get("target"), source_slug),
                            PREAMBLE_EXTRACTED,
                            relation_type,
                            link.get("value", 1),
                        )
                    )
            continue

        relation_type = RELATION_IMPLICIT_DEPENDENCY if link_type == BODY_EXTRACTED_LLM else RELATION_REFERENCE
        for link in links or []:
            edges.append(
                make_dependency_edge(
                    _link_endpoint_to_graph_key(link.get("source"), source_slug),
                    _link_endpoint_to_graph_key(link.get("target"), source_slug),
                    link_type,
                    str(link.get("relation_type") or relation_type),
                    link.get("value", 1),
                    **{
                        key: value
                        for key, value in link.items()
                        if key not in {"source", "target", "value", "relation_type"}
                    },
                )
            )

    return edges


def normalize_dependency_edges(network_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    edges = network_data.get("dependency_edges")
    if isinstance(edges, list):
        return [
            make_dependency_edge(
                edge.get("source"),
                edge.get("target"),
                str(edge.get("extraction_method") or ""),
                str(edge.get("relation_type") or ""),
                edge.get("value", 1),
                **{
                    key: value
                    for key, value in edge.items()
                    if key not in EDGE_BASE_FIELDS
                },
            )
            for edge in edges
            if edge.get("source") is not None and edge.get("target") is not None
        ]
    return []


def _ground_truth_source_configs_by_slug(ecosystem_slug: str | None) -> Dict[str, Dict[str, Any]]:
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
) -> tuple[str, str] | None:
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

    normalized = _normalize_reference_id(proposal_id, source_config)
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


def load_ground_truth_curated_entries(ecosystem_slug: str | None, *, strict: bool = True) -> List[Dict[str, str]]:
    if not ecosystem_slug:
        return []

    csv_path = Path("ip_data") / str(ecosystem_slug) / "ground_truth" / "interrelations.csv"
    if not csv_path.exists():
        return []

    lines = [
        line
        for line in csv_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not lines:
        return []

    reader = csv.DictReader(io.StringIO("\n".join(lines)), skipinitialspace=True)
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
        if not normalized.get("source") or not normalized.get("target"):
            continue
        entries.append({
            **{column: normalized.get(column, "") for column in GROUND_TRUTH_CSV_COLUMNS},
            "__line__": reader.line_num,
        })

    if strict:
        source_configs_by_slug = _ground_truth_source_configs_by_slug(ecosystem_slug)
        errors = validate_ground_truth_curated_entries(
            entries,
            source_configs_by_slug=source_configs_by_slug,
        )
        if errors:
            raise ValueError(
                f"Ground-truth validation failed for `{csv_path}`:\n- " + "\n- ".join(errors)
            )

    return entries


def normalize_proposal_ids(field: Any, proposal_label: str = "IP") -> List[str]:
    if not field:
        return []

    if isinstance(field, list):
        raw_items = field
    else:
        raw_items = str(field).split(",")

    result = []
    label = re.escape(proposal_label)
    id_pattern = re.compile(rf"^\s*(?:{label}[-\s]*)?[0-9A-Fa-f]+\s*$", re.IGNORECASE)
    uses_hex_ids = proposal_label.upper() == "NIP"

    for item in raw_items:
        text = str(item)
        if id_pattern.match(text):
            normalized = re.sub(rf"(?i)^\s*{label}[-\s]*", "", text).strip()
            if uses_hex_ids:
                normalized = normalized.upper()
                result.append(normalized.zfill(2) if len(normalized) == 1 else normalized)
            else:
                try:
                    result.append(str(int(normalized)))
                except ValueError:
                    result.append(normalized.upper())
    return result


def _uses_hex_proposal_ids(proposal_label: str = "IP", reference_pattern: str = "") -> bool:
    return uses_hex_proposal_ids(proposal_label, reference_pattern)


def _source_reference_configs(
    context: SourceContext,
    proposal_label: str = "IP",
) -> List[Dict[str, Any]]:
    configs: List[Dict[str, Any]] = []
    for source_slug, source_config in context.ecosystem_source_configs.items():
        label = str(source_config.get("proposal_acronym") or "").strip()
        pattern = str(source_config.get("reference_pattern") or "").strip()
        if not label:
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
                "proposal_label": proposal_label,
                "reference_pattern": context.reference_pattern,
                "max_proposal_id": context.max_proposal_id,
            }
        )

    return configs


def _normalize_reference_id(value: Any, config: Mapping[str, Any]) -> str | None:
    return normalize_reference_id_for_config(value, config)


def _reference_id_chars(config: Mapping[str, Any]) -> str:
    return r"[0-9A-Fa-f]" if _uses_hex_proposal_ids(
        str(config.get("proposal_label") or "IP"),
        str(config.get("reference_pattern") or ""),
    ) else r"\d"


def _resolve_reference_item(
    item: Any,
    reference_configs: List[Dict[str, Any]],
    active_config: Dict[str, Any],
) -> Dict[str, str] | None:
    if isinstance(item, dict):
        raw_source = (
            item.get("target_source")
            or item.get("source_slug")
            or item.get("graph_source")
            or item.get("source")
        )
        raw_id = item.get("target_id") or item.get("proposal_id") or item.get("id") or item.get("target")
        if raw_id is None:
            return None
        if raw_source is None and isinstance(raw_id, str) and ":" in raw_id:
            raw_source, raw_id = raw_id.split(":", 1)
        if raw_source is None and isinstance(raw_id, str):
            resolved = _resolve_reference_item(raw_id, reference_configs, active_config)
            if resolved is not None:
                if item.get("count") is not None:
                    resolved["count"] = item.get("count")
                return resolved
        matching_config = next(
            (config for config in reference_configs if str(config.get("source_slug")) == str(raw_source)),
            active_config,
        )
        normalized_id = _normalize_reference_id(raw_id, matching_config)
        if normalized_id is None:
            return None
        return {
            "source_slug": str(matching_config.get("source_slug") or ""),
            "proposal_id": normalized_id,
            **({"count": item.get("count")} if item.get("count") is not None else {}),
        }

    text = str(item).strip()
    if not text:
        return None

    for config in reference_configs:
        label = re.escape(str(config.get("proposal_label") or ""))
        if not label:
            continue
        id_chars = _reference_id_chars(config)
        match = re.match(rf"(?i)^\s*{label}[-#\s]*({id_chars}+)\s*$", text)
        if not match:
            continue
        normalized_id = _normalize_reference_id(match.group(1), config)
        if normalized_id is None:
            return None
        return {
            "source_slug": str(config.get("source_slug") or ""),
            "proposal_id": normalized_id,
        }

    id_chars = _reference_id_chars(active_config)
    match = re.match(rf"(?i)^\s*({id_chars}+)\s*$", text)
    if not match:
        return None
    normalized_id = _normalize_reference_id(match.group(1), active_config)
    if normalized_id is None:
        return None
    return {
        "source_slug": str(active_config.get("source_slug") or ""),
        "proposal_id": normalized_id,
    }


def normalize_proposal_references(
    field: Any,
    proposal_label: str = "IP",
    source_context: SourceContext | None = None,
) -> List[Dict[str, str]]:
    if not field:
        return []

    context = source_context or SourceContext.default()
    reference_configs = _source_reference_configs(context, proposal_label=proposal_label)
    active_config = next(
        (
            config
            for config in reference_configs
            if str(config.get("source_slug")) == str(context.source_slug)
        ),
        reference_configs[0],
    )
    raw_items = field if isinstance(field, list) else str(field).split(",")
    references: List[Dict[str, str]] = []
    seen = set()

    for item in raw_items:
        reference = _resolve_reference_item(item, reference_configs, active_config)
        if reference is None:
            continue
        key = (reference["source_slug"], reference["proposal_id"])
        if key in seen:
            continue
        seen.add(key)
        references.append(reference)

    return references


def _apply_alias(value: Any, aliases: Dict[str, str]) -> Any:
    if value is None:
        return None
    return aliases.get(value, value)


def load_proposal_json_documents(
    source_dir: Path,
    source_context: SourceContext | None = None,
) -> List[Dict[str, Any]]:
    documents: List[Dict[str, Any]] = []
    for file_path in sorted(source_dir.glob("*.json")):
        try:
            with file_path.open("r", encoding="utf-8") as handle:
                documents.append(normalize_proposal_document(json.load(handle), source_context=source_context))
        except json.JSONDecodeError:
            continue
    return documents


def build_network_data(
    proposal_data: Iterable[Dict[str, Any]],
    id_field: str = "id",
    proposal_label: str = "IP",
    source_context: SourceContext | None = None,
    known_proposal_ids_by_source: Mapping[str, set[str]] | None = None,
    ground_truth_entries: Sequence[Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    context = source_context or SourceContext.default()
    proposals = list(proposal_data)
    classification_fields: List[str] = context.classification_fields
    classification_aliases: Dict[str, Dict[str, str]] = {
        field: dict(context.classification_aliases(field))
        for field in classification_fields
    }
    layer_aliases = dict(context.classification_aliases("layer"))
    status_aliases = dict(context.classification_aliases("status"))
    type_aliases = dict(context.classification_aliases("type"))
    nodes = []
    explicit_reference_links = []
    implicit_dependency_links = []
    ground_truth_links = []
    explicit_dependency_links: Dict[str, List[Dict[str, Any]]] = {
        relation_type: [] for relation_type in context.preamble_interrelation_types
    }
    node_ids = set()
    known_ids_by_source = {
        str(source_slug): {str(proposal_id) for proposal_id in proposal_ids}
        for source_slug, proposal_ids in (known_proposal_ids_by_source or {}).items()
    }

    def target_exists(source_id: str, target_source_slug: str | None, target_id: str) -> bool:
        source_slug = str(target_source_slug or context.source_slug or "")
        if source_slug == str(context.source_slug or "") and target_id == source_id:
            return False
        if source_slug == str(context.source_slug or ""):
            return target_id in node_ids
        if source_slug in known_ids_by_source:
            return target_id in known_ids_by_source[source_slug]
        return True

    def make_link(
        source_id: str,
        target_source_slug: str | None,
        target_id: str,
        value: Any = 1,
        **extra: Any,
    ) -> Dict[str, Any]:
        return {
            "source": build_graph_key(context.source_slug, source_id),
            "target": build_graph_key(target_source_slug or context.source_slug, target_id),
            "value": value,
            **extra,
        }

    for proposal in proposals:
        if not proposal:
            continue

        preamble = proposal.get("raw", {}).get("preamble", {})
        formal_compliance = get_formal_compliance(proposal)
        insights = proposal.get("insights", {})
        proposal_id = preamble.get(id_field)

        if not proposal_id:
            continue

        proposal_id = str(proposal_id)
        graph_key = build_graph_key(context.source_slug, proposal_id)
        if proposal_id not in node_ids:
            git_history = proposal.get("meta", {}).get("git_history", [])
            node: Dict[str, Any] = {
                "id": proposal_id,
                "graph_key": graph_key,
                "title": preamble.get("title"),
                "compliance_score": formal_compliance.get("score", preamble.get("compliance_score")),
                "created": preamble.get("created"),
                "author": preamble.get("author"),
                "word_list": insights.get("word_list"),
            }

            # Derive author from committers present on the file's first day (e.g. NIPs)
            if not node.get("author"):
                first_day_authors = get_git_authors_on_first_day(git_history)
                if first_day_authors:
                    node["author"] = first_day_authors

            # Derive created date from oldest git commit when preamble has none
            if not node.get("created") and git_history:
                _oldest = git_history[-1]  # history is newest-first
                if len(_oldest) >= 2:
                    _ymd = _parse_date_ymd(_oldest[1])
                    if _ymd:
                        node["created"] = _ymd
            for field in classification_fields:
                node[field] = _apply_alias(preamble.get(field), classification_aliases[field])
            # Backward-compat aliases for ecosystems that don't define layer/type/status explicitly.
            node.setdefault("layer", _apply_alias(preamble.get("layer"), layer_aliases))
            node.setdefault("status", _apply_alias(preamble.get("status"), status_aliases))
            node.setdefault("type", _apply_alias(preamble.get("type"), type_aliases))
            nodes.append(node)
            node_ids.add(proposal_id)

    for proposal in proposals:
        if not proposal:
            continue

        preamble = proposal.get("raw", {}).get("preamble", {})
        interrelations = get_interrelations(proposal)
        proposal_id = preamble.get(id_field)

        if not proposal_id:
            continue

        proposal_id = str(proposal_id)
        if proposal_id not in node_ids:
            continue

        references_field = interrelations.get(BODY_EXTRACTED_REGEX)

        for ref in normalize_proposal_references(references_field, proposal_label=proposal_label, source_context=context):
            if target_exists(proposal_id, ref.get("source_slug"), ref["proposal_id"]):
                explicit_reference_links.append(make_link(proposal_id, ref.get("source_slug"), ref["proposal_id"], ref.get("count", 1)))

        for dep in normalize_proposal_references(
            interrelations.get(BODY_EXTRACTED_LLM),
            proposal_label=proposal_label,
            source_context=context,
        ):
            if target_exists(proposal_id, dep.get("source_slug"), dep["proposal_id"]):
                implicit_dependency_links.append(make_link(proposal_id, dep.get("source_slug"), dep["proposal_id"]))

        preamble_interrelations = interrelations.get(PREAMBLE_EXTRACTED, [])
        relation_entries_by_type: Dict[str, List[Any]] = {}
        if isinstance(preamble_interrelations, list):
            for entry in preamble_interrelations:
                if not isinstance(entry, dict):
                    continue
                relation_type = str(entry.get("type") or "").strip()
                if not relation_type:
                    continue
                relation_entries_by_type.setdefault(relation_type, []).append(entry)

        for relation_type, relation_entries in relation_entries_by_type.items():
            explicit_dependency_links.setdefault(relation_type, [])
            for ref in normalize_proposal_references(
                relation_entries,
                proposal_label=proposal_label,
                source_context=context,
            ):
                if target_exists(proposal_id, ref.get("source_slug"), ref["proposal_id"]):
                    explicit_dependency_links[relation_type].append(
                        make_link(proposal_id, ref.get("source_slug"), ref["proposal_id"])
                    )

    source_configs_by_slug = {
        str(config.get("source_slug") or ""): config
        for config in _source_reference_configs(context, proposal_label=proposal_label)
    }
    curated_entries = list(ground_truth_entries) if ground_truth_entries is not None else load_ground_truth_curated_entries(context.ecosystem_slug)
    for entry in curated_entries:
        if not isinstance(entry, Mapping):
            continue
        raw_source = str(entry.get("source") or "").strip()
        raw_target = str(entry.get("target") or "").strip()
        if ":" not in raw_source or ":" not in raw_target:
            continue

        source_source_slug, source_id_text = raw_source.split(":", 1)
        target_source_slug, target_id_text = raw_target.split(":", 1)
        source_config = source_configs_by_slug.get(source_source_slug)
        target_config = source_configs_by_slug.get(target_source_slug)
        if source_config is None or target_config is None:
            continue

        source_id = _normalize_reference_id(source_id_text, source_config)
        target_id = _normalize_reference_id(target_id_text, target_config)
        if source_id is None or target_id is None:
            continue
        if source_source_slug != str(context.source_slug or ""):
            continue
        if source_id not in node_ids:
            continue
        if not target_exists(source_id, target_source_slug, target_id):
            continue

        ground_truth_links.append(
            make_link(
                source_id,
                target_source_slug,
                target_id,
                relation_type=str(entry.get("relation_type") or "").strip() or "references",
                confidence=str(entry.get("confidence") or "").strip() or None,
                evidence=str(entry.get("evidence") or "").strip() or None,
                note=str(entry.get("note") or "").strip() or None,
                reviewer=str(entry.get("reviewer") or "").strip() or None,
                reviewed_at=str(entry.get("reviewed_at") or "").strip() or None,
            )
        )

    raw_links = {
        BODY_EXTRACTED_REGEX: explicit_reference_links,
        PREAMBLE_EXTRACTED: explicit_dependency_links,
        BODY_EXTRACTED_LLM: implicit_dependency_links,
        GROUND_TRUTH_CURATED: ground_truth_links,
    }
    dependency_edges = dependency_edges_from_links(raw_links, source_slug=context.source_slug)

    return {
        "nodes": nodes,
        "dependency_edges": dependency_edges,
    }


def save_network_data_artifacts(network_data: Dict[str, Any], output_stem: Path) -> None:
    output_stem.parent.mkdir(parents=True, exist_ok=True)

    json_path = output_stem.with_suffix(".json")

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(network_data, handle, ensure_ascii=False, indent=2)

    nodes_csv_path = output_stem.parent / f"{output_stem.name}_nodes.csv"
    with nodes_csv_path.open("w", encoding="utf-8", newline="") as handle:
        _base = ["id", "title", "compliance_score", "created", "author"]
        reserved = set(_base) | {"word_list"}
        node_fields = {
            key
            for node in network_data.get("nodes", [])
            for key in node.keys()
            if key not in reserved
        }
        _class = sorted(node_fields | {"layer", "status", "type"})
        fieldnames = _base + _class
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for node in network_data.get("nodes", []):
            row = {k: node.get(k) for k in fieldnames}
            if isinstance(row.get("author"), list):
                row["author"] = " | ".join(str(a) for a in row["author"])
            writer.writerow(row)

    dependency_edges = normalize_dependency_edges(network_data)
    dependency_edges_path = output_stem.parent / f"{output_stem.name}_dependency_edges.csv"
    with dependency_edges_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["source", "target", "extraction_method", "relation_type", "value"],
        )
        writer.writeheader()
        for edge in dependency_edges:
            writer.writerow(
                {
                    "source": edge.get("source"),
                    "target": edge.get("target"),
                    "extraction_method": edge.get("extraction_method"),
                    "relation_type": edge.get("relation_type"),
                    "value": edge.get("value", 1),
                }
            )
