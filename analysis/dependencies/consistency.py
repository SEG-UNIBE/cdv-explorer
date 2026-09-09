from collections.abc import Iterable, Mapping
from typing import Any

import networkx as nx

from analysis.dependencies.constants import BODY_EXTRACTED_LLM, PREAMBLE_EXTRACTED

APPROACH_SPECS: tuple[dict[str, Any], ...] = (
    {
        "key": PREAMBLE_EXTRACTED,
        "label": "Preamble",
        "dependency_types": frozenset({"requires"}),
        "successor_to_predecessor": frozenset({"replaces"}),
        "predecessor_to_successor": frozenset({"proposed_replacement"}),
    },
    {
        "key": BODY_EXTRACTED_LLM,
        "label": "LLM",
        "dependency_types": frozenset({"depends_on"}),
        "successor_to_predecessor": frozenset({"supersedes"}),
        "predecessor_to_successor": frozenset({"superseded_by"}),
    },
)


def _graph_key_sort_key(value: str) -> tuple[str, int, str]:
    source_slug, separator, proposal_id = value.partition(":")
    if separator and proposal_id.isdigit():
        return source_slug, int(proposal_id), ""
    return source_slug if separator else "", 0, proposal_id if separator else value


def _sorted_graph_keys(values: Iterable[str]) -> list[str]:
    return sorted(set(values), key=_graph_key_sort_key)


def _edge_sort_key(edge: tuple[str, str]) -> tuple[tuple[str, int, str], tuple[str, int, str]]:
    return _graph_key_sort_key(edge[0]), _graph_key_sort_key(edge[1])


def _nontrivial_components(edges: set[tuple[str, str]]) -> list[list[str]]:
    graph = nx.DiGraph()
    graph.add_edges_from(edges)
    components = [
        _sorted_graph_keys(component)
        for component in nx.strongly_connected_components(graph)
        if len(component) > 1
    ]
    return sorted(components, key=lambda component: _graph_key_sort_key(component[0]))


def _node_title_map(network_data: Mapping[str, Any]) -> dict[str, str]:
    titles: dict[str, str] = {}
    for node in network_data.get("nodes", []):
        if not isinstance(node, Mapping):
            continue
        graph_key = str(
            node.get("graph_key") or node.get("graphId") or node.get("id") or ""
        ).strip()
        if graph_key:
            titles[graph_key] = str(node.get("title") or "").strip()
    return titles


def _case_node(graph_key: str, titles: Mapping[str, str]) -> dict[str, str]:
    return {"id": graph_key, "title": titles.get(graph_key, "")}


def _component_cases(
    components: list[list[str]], titles: Mapping[str, str]
) -> list[dict[str, Any]]:
    return [
        {"nodes": [_case_node(graph_key, titles) for graph_key in component]}
        for component in components
    ]


def _percentage(count: int, total: int) -> float:
    return round((count / total) * 100, 1) if total else 0.0


def _count_share_display(count: int, total: int) -> str:
    return f"{count} ({_percentage(count, total):.1f}%)" if total else str(count)


def _human_join(values: list[str]) -> str:
    normalized = [value[:1].lower() + value[1:] for value in values]
    if len(normalized) < 2:
        return "".join(normalized)
    if len(normalized) == 2:
        return " or ".join(normalized)
    return f"{', '.join(normalized[:-1])}, or {normalized[-1]}"


def _build_approach_analysis(
    network_data: Mapping[str, Any], spec: Mapping[str, Any]
) -> dict[str, Any]:
    method = str(spec["key"])
    dependency_types = set(spec["dependency_types"])
    successor_to_predecessor = set(spec["successor_to_predecessor"])
    predecessor_to_successor = set(spec["predecessor_to_successor"])
    relevant_types = dependency_types | successor_to_predecessor | predecessor_to_successor

    node_keys = {
        str(node.get("graph_key") or node.get("graphId") or node.get("id") or "").strip()
        for node in network_data.get("nodes", [])
        if isinstance(node, Mapping)
    }
    node_keys.discard("")
    known_source_slugs = {key.partition(":")[0] for key in node_keys if ":" in key}
    titles = _node_title_map(network_data)

    dependency_edges: set[tuple[str, str]] = set()
    supersession_declarations: dict[tuple[str, str], set[str]] = {}
    self_relations: set[tuple[str, str, str]] = set()
    unresolved_targets: set[tuple[str, str, str]] = set()
    dependency_self_relations: set[tuple[str, str, str]] = set()
    supersession_self_relations: set[tuple[str, str, str]] = set()
    dependency_unresolved_targets: set[tuple[str, str, str]] = set()
    supersession_unresolved_targets: set[tuple[str, str, str]] = set()

    for raw_edge in network_data.get("dependency_edges", []):
        if not isinstance(raw_edge, Mapping):
            continue
        if str(raw_edge.get("extraction_method") or "") != method:
            continue

        relation_type = str(raw_edge.get("relation_type") or "").strip()
        if relation_type not in relevant_types:
            continue
        source = str(raw_edge.get("source") or "").strip()
        target = str(raw_edge.get("target") or "").strip()
        if not source or not target:
            continue
        is_dependency = relation_type in dependency_types

        if source == target:
            relation = (source, target, relation_type)
            self_relations.add(relation)
            (dependency_self_relations if is_dependency else supersession_self_relations).add(
                relation
            )

        target_slug = target.partition(":")[0] if ":" in target else ""
        if target_slug in known_source_slugs and target not in node_keys:
            relation = (source, target, relation_type)
            unresolved_targets.add(relation)
            (
                dependency_unresolved_targets
                if is_dependency
                else supersession_unresolved_targets
            ).add(relation)

        if is_dependency:
            dependency_edges.add((source, target))
            continue

        if relation_type in successor_to_predecessor:
            fact = (source, target)
            declaration_side = "successor_to_predecessor"
        else:
            fact = (target, source)
            declaration_side = "predecessor_to_successor"
        supersession_declarations.setdefault(fact, set()).add(declaration_side)

    dependency_components = _nontrivial_components(dependency_edges)
    dependency_component_nodes = {
        node for component in dependency_components for node in component
    }

    supersession_facts = set(supersession_declarations)
    supersession_components = _nontrivial_components(supersession_facts)
    reciprocal_facts = {
        fact
        for fact, sides in supersession_declarations.items()
        if sides == {"successor_to_predecessor", "predecessor_to_successor"}
    }
    one_sided_facts = supersession_facts - reciprocal_facts

    def fact_case(fact: tuple[str, str]) -> dict[str, Any]:
        successor, predecessor = fact
        return {
            "successor": _case_node(successor, titles),
            "predecessor": _case_node(predecessor, titles),
            "declaration_sides": sorted(supersession_declarations[fact]),
        }

    return {
        "key": method,
        "label": str(spec["label"]),
        "dependency": {
            "edge_count": len(dependency_edges),
            "cyclic_group_count": len(dependency_components),
            "involved_node_count": len(dependency_component_nodes),
            "self_relation_count": len(dependency_self_relations),
            "unresolved_target_count": len(dependency_unresolved_targets),
            "cyclic_groups": _component_cases(dependency_components, titles),
        },
        "supersession": {
            "fact_count": len(supersession_facts),
            "reciprocal_count": len(reciprocal_facts),
            "reciprocal_percentage": _percentage(
                len(reciprocal_facts), len(supersession_facts)
            ),
            "one_sided_count": len(one_sided_facts),
            "one_sided_percentage": _percentage(
                len(one_sided_facts), len(supersession_facts)
            ),
            "reciprocal_facts": [
                fact_case(fact) for fact in sorted(reciprocal_facts, key=_edge_sort_key)
            ],
            "one_sided_facts": [
                fact_case(fact) for fact in sorted(one_sided_facts, key=_edge_sort_key)
            ],
            "cyclic_group_count": len(supersession_components),
            "self_relation_count": len(supersession_self_relations),
            "unresolved_target_count": len(supersession_unresolved_targets),
            "cyclic_groups": _component_cases(supersession_components, titles),
        },
        "checks": {
            "self_relation_count": len(self_relations),
            "self_relations": [
                {"source": source, "target": target, "relation_type": relation_type}
                for source, target, relation_type in sorted(self_relations)
            ],
            "unresolved_target_count": len(unresolved_targets),
            "unresolved_targets": [
                {"source": source, "target": target, "relation_type": relation_type}
                for source, target, relation_type in sorted(unresolved_targets)
            ],
        },
    }


def build_dependency_consistency_payload(
    network_data: Mapping[str, Any],
) -> dict[str, Any]:
    """Build typed dependency and supersession consistency results once.

    Preamble and LLM are intentionally analyzed separately. Regex has no type
    signal, while curated ground truth covers only a reviewed sample.
    """
    analyses = [_build_approach_analysis(network_data, spec) for spec in APPROACH_SPECS]
    by_approach = {analysis["key"]: analysis for analysis in analyses}

    table_rows: list[dict[str, Any]] = [
        {
            "group": "Dependency",
            "metric": "Edges analyzed",
            "values": {
                analysis["key"]: str(analysis["dependency"]["edge_count"])
                for analysis in analyses
            },
        },
        {
            "group": "Dependency",
            "metric": "Cyclic groups (SCCs)",
            "values": {
                analysis["key"]: str(analysis["dependency"]["cyclic_group_count"])
                for analysis in analyses
            },
        },
        {
            "group": "Dependency",
            "metric": "IPs involved",
            "values": {
                analysis["key"]: str(analysis["dependency"]["involved_node_count"])
                for analysis in analyses
            },
        },
        {
            "group": "Supersession",
            "metric": "Distinct relations",
            "values": {
                analysis["key"]: str(analysis["supersession"]["fact_count"])
                for analysis in analyses
            },
        },
        {
            "group": "Supersession",
            "metric": "Reciprocally declared",
            "values": {
                analysis["key"]: _count_share_display(
                    analysis["supersession"]["reciprocal_count"],
                    analysis["supersession"]["fact_count"],
                )
                for analysis in analyses
            },
        },
        {
            "group": "Supersession",
            "metric": "One-sided declarations",
            "values": {
                analysis["key"]: _count_share_display(
                    analysis["supersession"]["one_sided_count"],
                    analysis["supersession"]["fact_count"],
                )
                for analysis in analyses
            },
        },
    ]

    structural_check_rows: list[dict[str, Any]] = [
        {
            "metric": "Self-relations",
            "values": {
                analysis["key"]: analysis["checks"]["self_relation_count"]
                for analysis in analyses
            },
        },
        {
            "metric": "Supersession cycles",
            "values": {
                analysis["key"]: analysis["supersession"]["cyclic_group_count"]
                for analysis in analyses
            },
        },
        {
            "metric": "Unresolved catalog targets",
            "values": {
                analysis["key"]: analysis["checks"]["unresolved_target_count"]
                for analysis in analyses
            },
        },
    ]
    omitted_zero_checks: list[str] = [
        row["metric"]
        for row in structural_check_rows
        if all(value == 0 for value in row["values"].values())
    ]
    table_rows.extend(
        {
            "group": "Additional checks",
            "metric": row["metric"],
            "values": {
                key: str(value) for key, value in row["values"].items()
            },
        }
        for row in structural_check_rows
        if row["metric"] not in omitted_zero_checks
    )

    dashboard_table_rows = [
        *[row for row in table_rows if row["group"] in {"Dependency", "Supersession"}],
        {
            "group": "Dependency",
            "metric": "Self-relations",
            "values": {
                analysis["key"]: str(analysis["dependency"]["self_relation_count"])
                for analysis in analyses
            },
        },
        {
            "group": "Supersession",
            "metric": "Cyclic groups (SCCs)",
            "values": {
                analysis["key"]: str(analysis["supersession"]["cyclic_group_count"])
                for analysis in analyses
            },
        },
    ]
    dashboard_metric_order = {
        "Dependency": (
            "Edges analyzed",
            "Cyclic groups (SCCs)",
            "IPs involved",
            "Self-relations",
        ),
        "Supersession": (
            "Distinct relations",
            "Reciprocally declared",
            "One-sided declarations",
            "Cyclic groups (SCCs)",
        ),
    }
    dashboard_table_rows.sort(
        key=lambda row: (
            0 if row["group"] == "Dependency" else 1,
            dashboard_metric_order[row["group"]].index(row["metric"]),
        )
    )

    return {
        "meta": {
            "schema_version": 2,
            "llm_model": str(network_data.get("llm_model") or "").strip() or None,
            "approach_order": [analysis["key"] for analysis in analyses],
        },
        "by_approach": by_approach,
        "table_rows": table_rows,
        "dashboard_table_rows": dashboard_table_rows,
        "structural_check_rows": structural_check_rows,
        "omitted_zero_checks": omitted_zero_checks,
        "omitted_zero_checks_text": (
            f"Neither network contains {_human_join(omitted_zero_checks)}."
            if omitted_zero_checks
            else ""
        ),
    }
