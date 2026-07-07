import json
import csv
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from analysis.reference_ids import (
    normalize_reference_id_for_config,
    uses_hex_proposal_ids,
)
from analysis.dependencies.constants import (
    BODY_EXTRACTED_LLM,
    BODY_EXTRACTED_REGEX,
    GROUND_TRUTH_CURATED,
    PREAMBLE_EXTRACTED,
)
from analysis.authorship.mining import get_git_authors_on_first_day
from analysis.proposal_schema import (
    get_formal_compliance,
    get_interrelations,
    is_successful_llm_run,
    is_llm_runs_format,
    normalize_proposal_document,
)
from analysis.validation.ground_truth import (
    load_ground_truth_curated_entries,
    load_ground_truth_ips,
)
from pipeline.source_context import SourceContext
from analysis.utils import parse_date_ymd as _parse_date_ymd

RELATION_REFERENCE = "reference"
RELATION_IMPLICIT_DEPENDENCY = "implicit_dependency"
EDGE_BASE_FIELDS = {"source", "target", "extraction_method", "relation_type", "value"}


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


def dependency_edges_from_links(
    links_by_type: Dict[str, Any], source_slug: str | None = None
) -> List[Dict[str, Any]]:
    edges: List[Dict[str, Any]] = []
    if not isinstance(links_by_type, dict):
        return edges

    for link_type, links in links_by_type.items():
        if link_type == PREAMBLE_EXTRACTED and isinstance(links, dict):
            for relation_type, subtype_links in links.items():
                for link in subtype_links or []:
                    edges.append(
                        make_dependency_edge(
                            _link_endpoint_to_graph_key(
                                link.get("source"), source_slug
                            ),
                            _link_endpoint_to_graph_key(
                                link.get("target"), source_slug
                            ),
                            PREAMBLE_EXTRACTED,
                            relation_type,
                            link.get("value", 1),
                        )
                    )
            continue

        relation_type = (
            RELATION_IMPLICIT_DEPENDENCY
            if link_type == BODY_EXTRACTED_LLM
            else RELATION_REFERENCE
        )
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


def available_llm_model_entries(
    network_data: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    llm_models = network_data.get("llm_models")
    if not isinstance(llm_models, Mapping):
        return []
    available = llm_models.get("available_models")
    if not isinstance(available, list):
        return []
    return [
        dict(entry)
        for entry in available
        if isinstance(entry, Mapping) and str(entry.get("model") or "").strip()
    ]


def collapse_network_data_to_llm_model(
    network_data: Dict[str, Any],
    llm_model: str | None,
) -> Dict[str, Any]:
    model = str(llm_model or "").strip()
    if not model:
        collapsed = dict(network_data)
        collapsed.pop("llm_models", None)
        collapsed.pop("llm_model", None)
        return collapsed

    llm_models = network_data.get("llm_models")
    if not isinstance(llm_models, Mapping):
        raise ValueError(
            "No per-model LLM artifact data is available in the dependency network payload."
        )

    edges_by_model = llm_models.get("dependency_edges_by_model")
    if not isinstance(edges_by_model, Mapping) or model not in edges_by_model:
        available = sorted(
            str(entry.get("model") or "").strip()
            for entry in available_llm_model_entries(network_data)
        )
        raise ValueError(
            f"LLM model '{model}' is not available in the dependency network payload. "
            f"Available models: {', '.join(available) if available else '(none)'}"
        )

    base_edges = [
        edge
        for edge in normalize_dependency_edges(network_data)
        if edge.get("extraction_method") != BODY_EXTRACTED_LLM
    ]
    model_edges = [
        make_dependency_edge(
            edge.get("source"),
            edge.get("target"),
            str(edge.get("extraction_method") or ""),
            str(edge.get("relation_type") or ""),
            edge.get("value", 1),
            **{
                key: value for key, value in edge.items() if key not in EDGE_BASE_FIELDS
            },
        )
        for edge in (edges_by_model.get(model) or [])
        if isinstance(edge, Mapping)
    ]

    collapsed = dict(network_data)
    collapsed["dependency_edges"] = base_edges + model_edges
    collapsed["llm_model"] = model
    collapsed.pop("llm_models", None)
    return collapsed


def _llm_runs_by_model(interrelations: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    raw_llm = interrelations.get(BODY_EXTRACTED_LLM)
    if not is_llm_runs_format(raw_llm):
        return {}
    runs_by_model: Dict[str, Dict[str, Any]] = {}
    for run in sorted(raw_llm, key=lambda item: str(item.get("timestamp") or "")):
        if not (
            isinstance(run, Mapping)
            and str(run.get("model") or "").strip()
            and is_successful_llm_run(run)
        ):
            continue
        runs_by_model[str(run.get("model") or "").strip()] = dict(run)
    return runs_by_model


def _default_llm_run(
    llm_runs_by_model: Mapping[str, Dict[str, Any]],
    configured_model: str | None,
) -> Dict[str, Any] | None:
    configured = str(configured_model or "").strip()
    if configured and configured in llm_runs_by_model:
        return llm_runs_by_model[configured]
    if not llm_runs_by_model:
        return None
    return max(
        llm_runs_by_model.values(),
        key=lambda run: str(run.get("timestamp") or ""),
    )


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
                result.append(
                    normalized.zfill(2) if len(normalized) == 1 else normalized
                )
            else:
                try:
                    result.append(str(int(normalized)))
                except ValueError:
                    result.append(normalized.upper())
    return result


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
    return (
        r"[0-9A-Fa-f]"
        if uses_hex_proposal_ids(
            str(config.get("proposal_label") or "IP"),
            str(config.get("reference_pattern") or ""),
        )
        else r"\d"
    )


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
        raw_id = (
            item.get("target_id")
            or item.get("proposal_id")
            or item.get("id")
            or item.get("target")
        )
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
            (
                config
                for config in reference_configs
                if str(config.get("source_slug")) == str(raw_source)
            ),
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
    reference_configs = _source_reference_configs(
        context, proposal_label=proposal_label
    )
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
                documents.append(
                    normalize_proposal_document(
                        json.load(handle), source_context=source_context
                    )
                )
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
    reviewed_ips_entries: Sequence[Mapping[str, Any]] | None = None,
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
    implicit_dependency_links_by_model: Dict[str, List[Dict[str, Any]]] = {}
    llm_model_stats: Dict[str, Dict[str, Any]] = {}
    ground_truth_links = []
    explicit_dependency_links: Dict[str, List[Dict[str, Any]]] = {
        relation_type: [] for relation_type in context.preamble_interrelation_types
    }
    node_ids = set()
    known_ids_by_source = {
        str(source_slug): {str(proposal_id) for proposal_id in proposal_ids}
        for source_slug, proposal_ids in (known_proposal_ids_by_source or {}).items()
    }

    def target_exists(
        source_id: str, target_source_slug: str | None, target_id: str
    ) -> bool:
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
            "target": build_graph_key(
                target_source_slug or context.source_slug, target_id
            ),
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
                "compliance_score": formal_compliance.get(
                    "score", preamble.get("compliance_score")
                ),
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
                node[field] = _apply_alias(
                    preamble.get(field), classification_aliases[field]
                )
            # Backward-compat aliases for ecosystems that don't define layer/type/status explicitly.
            node.setdefault("layer", _apply_alias(preamble.get("layer"), layer_aliases))
            node.setdefault(
                "status", _apply_alias(preamble.get("status"), status_aliases)
            )
            node.setdefault("type", _apply_alias(preamble.get("type"), type_aliases))
            nodes.append(node)
            node_ids.add(proposal_id)

    for proposal in proposals:
        if not proposal:
            continue

        preamble = proposal.get("raw", {}).get("preamble", {})
        interrelations = get_interrelations(proposal)
        raw_interrelations = proposal.get("insights", {}).get("interrelations", {})
        proposal_id = preamble.get(id_field)

        if not proposal_id:
            continue

        proposal_id = str(proposal_id)
        if proposal_id not in node_ids:
            continue

        references_field = interrelations.get(BODY_EXTRACTED_REGEX)

        for ref in normalize_proposal_references(
            references_field, proposal_label=proposal_label, source_context=context
        ):
            if target_exists(proposal_id, ref.get("source_slug"), ref["proposal_id"]):
                explicit_reference_links.append(
                    make_link(
                        proposal_id,
                        ref.get("source_slug"),
                        ref["proposal_id"],
                        ref.get("count", 1),
                    )
                )

        llm_runs_by_model = _llm_runs_by_model(raw_interrelations)
        default_llm_run = _default_llm_run(llm_runs_by_model, context.llm_model)
        for llm_model, llm_run in llm_runs_by_model.items():
            llm_model_stats.setdefault(
                llm_model,
                {
                    "model": llm_model,
                    "document_count": 0,
                    "edge_count": 0,
                },
            )
            llm_model_stats[llm_model]["document_count"] += 1
            model_links = implicit_dependency_links_by_model.setdefault(llm_model, [])
            for dep in normalize_proposal_references(
                llm_run.get("dependencies"),
                proposal_label=proposal_label,
                source_context=context,
            ):
                if not target_exists(
                    proposal_id, dep.get("source_slug"), dep["proposal_id"]
                ):
                    continue
                edge = make_link(
                    proposal_id,
                    dep.get("source_slug"),
                    dep["proposal_id"],
                    llm_model=llm_model,
                )
                model_links.append(edge)
                llm_model_stats[llm_model]["edge_count"] += 1
                if default_llm_run is llm_run:
                    implicit_dependency_links.append(edge)

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
                if target_exists(
                    proposal_id, ref.get("source_slug"), ref["proposal_id"]
                ):
                    explicit_dependency_links[relation_type].append(
                        make_link(
                            proposal_id, ref.get("source_slug"), ref["proposal_id"]
                        )
                    )

    source_configs_by_slug = {
        str(config.get("source_slug") or ""): config
        for config in _source_reference_configs(context, proposal_label=proposal_label)
    }
    curated_entries = (
        list(ground_truth_entries)
        if ground_truth_entries is not None
        else load_ground_truth_curated_entries(context.ecosystem_slug)
    )
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
                relation_type=str(entry.get("relation_type") or "").strip()
                or "references",
                confidence=str(entry.get("confidence") or "").strip() or None,
                evidence=str(entry.get("evidence") or "").strip() or None,
                note=str(entry.get("note") or "").strip() or None,
                reviewer=str(entry.get("reviewer") or "").strip() or None,
                reviewed_at=str(entry.get("reviewed_at") or "").strip() or None,
            )
        )

    reviewed_ip_rows = (
        list(reviewed_ips_entries)
        if reviewed_ips_entries is not None
        else load_ground_truth_ips(context.ecosystem_slug)
    )
    ground_truth_reviewed_ips = []
    seen_reviewed_ips: set[str] = set()
    for entry in reviewed_ip_rows:
        if not isinstance(entry, Mapping):
            continue
        raw_ip = str(entry.get("ip") or "").strip()
        if ":" not in raw_ip:
            continue
        ip_source_slug, ip_id_text = raw_ip.split(":", 1)
        source_config = source_configs_by_slug.get(ip_source_slug)
        if source_config is None:
            continue
        ip_id = _normalize_reference_id(ip_id_text, source_config)
        if ip_id is None:
            continue
        if ip_source_slug != str(context.source_slug or ""):
            continue
        if ip_id not in node_ids:
            continue

        graph_key = build_graph_key(ip_source_slug, ip_id)
        if graph_key in seen_reviewed_ips:
            continue
        seen_reviewed_ips.add(graph_key)
        ground_truth_reviewed_ips.append(
            {
                "ip": graph_key,
                "proposal_id": ip_id,
                "source_slug": ip_source_slug,
                "reviewer": str(entry.get("reviewer") or "").strip() or None,
                "reviewed_at": str(entry.get("reviewed_at") or "").strip() or None,
                "sampling_strategy": str(entry.get("sampling_strategy") or "").strip()
                or None,
                "sampling_snapshot": str(entry.get("sampling_snapshot") or "").strip()
                or None,
                "sampling_seed": str(entry.get("sampling_seed") or "").strip() or None,
                "era_bucket": str(entry.get("era_bucket") or "").strip() or None,
                "density_bucket": str(entry.get("density_bucket") or "").strip()
                or None,
                "density_basis": str(entry.get("density_basis") or "").strip() or None,
                "created": str(entry.get("created") or "").strip() or None,
                "status": str(entry.get("status") or "").strip() or None,
                "type": str(entry.get("type") or "").strip() or None,
                "layer": str(entry.get("layer") or "").strip() or None,
                "title": str(entry.get("title") or "").strip() or None,
                "extracted_target_count": str(
                    entry.get("extracted_target_count") or ""
                ).strip()
                or None,
                "note": str(entry.get("note") or "").strip() or None,
            }
        )

    raw_links = {
        BODY_EXTRACTED_REGEX: explicit_reference_links,
        PREAMBLE_EXTRACTED: explicit_dependency_links,
        BODY_EXTRACTED_LLM: implicit_dependency_links,
        GROUND_TRUTH_CURATED: ground_truth_links,
    }
    dependency_edges = dependency_edges_from_links(
        raw_links, source_slug=context.source_slug
    )
    dependency_edges_by_model = {
        model: dependency_edges_from_links(
            {BODY_EXTRACTED_LLM: links},
            source_slug=context.source_slug,
        )
        for model, links in implicit_dependency_links_by_model.items()
    }
    default_model = str(context.llm_model or "").strip()
    if not default_model and llm_model_stats:
        default_model = sorted(llm_model_stats)[0]

    return {
        "nodes": nodes,
        "dependency_edges": dependency_edges,
        "llm_models": {
            "default_model": default_model or None,
            "available_models": sorted(
                llm_model_stats.values(),
                key=lambda item: str(item.get("model") or ""),
            ),
            "dependency_edges_by_model": dependency_edges_by_model,
        },
        "ground_truth_reviewed_ips": ground_truth_reviewed_ips,
    }


def save_network_data_artifacts(
    network_data: Dict[str, Any], output_stem: Path, include_json: bool = True
) -> None:
    output_stem.parent.mkdir(parents=True, exist_ok=True)

    if include_json:
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
    dependency_edges_path = (
        output_stem.parent / f"{output_stem.name}_dependency_edges.csv"
    )
    with dependency_edges_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source",
                "target",
                "extraction_method",
                "relation_type",
                "value",
            ],
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
