import json
import csv
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

from analysis.dependencies.constants import (
    BODY_EXTRACTED_LLM,
    BODY_EXTRACTED_REGEX,
    PREAMBLE_EXTRACTED,
)
from analysis.authorship.mining import get_git_authors_on_first_day
from analysis.proposal_schema import (
    get_formal_compliance,
    get_interrelations,
    get_preamble_interrelations,
    normalize_proposal_document,
)
from pipeline.source_context import SourceContext
from analysis.utils import parse_date_ymd as _parse_date_ymd

RELATION_REFERENCE = "reference"
RELATION_IMPLICIT_DEPENDENCY = "implicit_dependency"


def build_graph_key(source_slug: str | None, proposal_id: Any) -> str:
    return f"{source_slug}:{proposal_id}" if source_slug else str(proposal_id)


def make_dependency_edge(
    source: Any,
    target: Any,
    extraction_method: str,
    relation_type: str,
    value: Any = 1,
) -> Dict[str, Any]:
    return {
        "source": str(source),
        "target": str(target),
        "extraction_method": extraction_method,
        "relation_type": relation_type,
        "value": value,
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
                    relation_type,
                    link.get("value", 1),
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
            )
            for edge in edges
            if edge.get("source") is not None and edge.get("target") is not None
        ]
    return []


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
) -> Dict[str, Any]:
    context = source_context or SourceContext.default()
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
    requires_links = []
    replaces_links = []
    proposed_replacement_links = []
    node_ids = set()

    for proposal in proposal_data:
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

    for proposal in proposal_data:
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

        for ref_id in normalize_proposal_ids(references_field, proposal_label=proposal_label):
            if ref_id in node_ids:
                explicit_reference_links.append({"source": proposal_id, "target": ref_id, "value": 1})

        for dep_id in normalize_proposal_ids(interrelations.get(BODY_EXTRACTED_LLM), proposal_label=proposal_label):
            if dep_id in node_ids:
                implicit_dependency_links.append({"source": proposal_id, "target": dep_id, "value": 1})

        preamble_interrelations = get_preamble_interrelations(preamble, source_context=context)

        for req_id in normalize_proposal_ids(preamble_interrelations.get("requires"), proposal_label=proposal_label):
            if req_id in node_ids:
                requires_links.append({"source": proposal_id, "target": req_id, "value": 1})

        for rep_id in normalize_proposal_ids(preamble_interrelations.get("replaces"), proposal_label=proposal_label):
            if rep_id in node_ids:
                replaces_links.append({"source": proposal_id, "target": rep_id, "value": 1})

        for sup_id in normalize_proposal_ids(
            preamble_interrelations.get("proposed_replacement"),
            proposal_label=proposal_label,
        ):
            if sup_id in node_ids:
                proposed_replacement_links.append({"source": proposal_id, "target": sup_id, "value": 1})

    explicit_dependency_links = {
        "requires": requires_links,
        "replaces": replaces_links,
        "proposed_replacement": proposed_replacement_links,
    }
    raw_links = {
        BODY_EXTRACTED_REGEX: explicit_reference_links,
        PREAMBLE_EXTRACTED: explicit_dependency_links,
        BODY_EXTRACTED_LLM: implicit_dependency_links,
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
