from typing import Any, Dict, Iterable, List

import networkx as nx

from analysis.dependencies.constants import (
    BODY_EXTRACTED_LLM,
    BODY_EXTRACTED_REGEX,
    DEPENDENCY_APPROACH_LABELS,
    DEPENDENCY_APPROACH_ORDER,
    PREAMBLE_EXTRACTED,
)


def _canonical_dependency_edges(network_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    edges = network_data.get("dependency_edges")
    if not isinstance(edges, list):
        return []
    return [
        edge
        for edge in edges
        if isinstance(edge, dict) and edge.get("source") is not None and edge.get("target") is not None
    ]


def _links_for_type(network_data: Dict[str, Any], link_type: str) -> List[Dict[str, Any]]:
    dependency_edges = _canonical_dependency_edges(network_data)
    if link_type == PREAMBLE_EXTRACTED:
        return [
            edge
            for edge in dependency_edges
            if edge.get("extraction_method") == PREAMBLE_EXTRACTED
        ]

    if link_type in (BODY_EXTRACTED_REGEX, BODY_EXTRACTED_LLM):
        return [
            edge
            for edge in dependency_edges
            if edge.get("extraction_method") == link_type
        ]

    return [
        edge
        for edge in dependency_edges
        if edge.get("extraction_method") == PREAMBLE_EXTRACTED
        and edge.get("relation_type") == link_type
    ]


def _split_graph_key(value: Any) -> tuple[str | None, str]:
    text = str(value)
    if ":" not in text:
        return None, text
    source_slug, proposal_id = text.split(":", 1)
    return source_slug or None, proposal_id


def _canonical_node_ids(network_data: Dict[str, Any]) -> Dict[str, str]:
    dependency_edges = _canonical_dependency_edges(network_data)
    edge_keys = {
        str(value)
        for edge in dependency_edges
        for value in (edge.get("source"), edge.get("target"))
        if value is not None
    }
    source_slugs = {
        source_slug
        for source_slug, _proposal_id in (_split_graph_key(value) for value in edge_keys)
        if source_slug
    }
    single_edge_source_slug = next(iter(source_slugs)) if len(source_slugs) == 1 else None

    node_ids: Dict[str, str] = {}
    for node in network_data.get("nodes", []):
        raw_id = str(node.get("id"))
        graph_key = node.get("graph_key") or node.get("graphId") or node.get("graph_id")
        if graph_key is not None:
            node_ids[raw_id] = str(graph_key)
            continue

        node_source_slug = node.get("graphSource") or node.get("source_slug") or node.get("sourceSlug")
        if node_source_slug:
            node_ids[raw_id] = f"{node_source_slug}:{raw_id}"
            continue

        matching_edge_keys = [
            key
            for key in edge_keys
            if _split_graph_key(key)[1] == raw_id
        ]
        if len(matching_edge_keys) == 1:
            node_ids[raw_id] = matching_edge_keys[0]
        elif single_edge_source_slug:
            node_ids[raw_id] = f"{single_edge_source_slug}:{raw_id}"
        else:
            node_ids[raw_id] = raw_id

    return node_ids


def build_graph(network_data: Dict[str, Any], link_type: str = BODY_EXTRACTED_REGEX) -> nx.DiGraph:
    graph = nx.DiGraph()
    use_canonical_edges = bool(_canonical_dependency_edges(network_data))
    node_id_map = _canonical_node_ids(network_data) if use_canonical_edges else {}

    for node in network_data.get("nodes", []):
        raw_id = str(node["id"])
        graph_id = node_id_map.get(raw_id, raw_id)
        graph.add_node(
            graph_id,
            title=node.get("title"),
            layer=node.get("layer"),
            compliance_score=node.get("compliance_score", 0),
            local_id=raw_id,
        )

    for link in _links_for_type(network_data, link_type):
        graph.add_edge(str(link["source"]), str(link["target"]))

    return graph


def compute_top_central_nodes(graph: nx.DiGraph, top_n: int = 5) -> Dict[str, List[Dict[str, float | str]]]:
    in_deg = sorted(nx.in_degree_centrality(graph).items(), key=lambda x: x[1], reverse=True)
    out_deg = sorted(nx.out_degree_centrality(graph).items(), key=lambda x: x[1], reverse=True)
    btw = sorted(nx.betweenness_centrality(graph).items(), key=lambda x: x[1], reverse=True)
    pr = sorted(nx.pagerank(graph).items(), key=lambda x: x[1], reverse=True)

    def _rows(items: Iterable[tuple[str, float]]) -> List[Dict[str, float | str]]:
        return [{"node": n, "score": float(c)} for n, c in list(items)[:top_n]]

    return {
        "in_degree": _rows(in_deg),
        "out_degree": _rows(out_deg),
        "betweenness": _rows(btw),
        "pagerank": _rows(pr),
    }


def compute_graph_depth(graph: nx.DiGraph) -> int:
    longest_path_length = 0
    for node in graph.nodes:
        if graph.in_degree(node) == 0:
            lengths = nx.single_source_shortest_path_length(graph, node)
            max_length = max(lengths.values(), default=0)
            longest_path_length = max(longest_path_length, max_length)
    return longest_path_length


def find_circular_dependencies(network_data: Dict[str, Any], link_type: str = BODY_EXTRACTED_REGEX) -> List[List[str]]:
    graph = build_graph(network_data, link_type=link_type)
    return [list(cycle) for cycle in nx.simple_cycles(graph)]


def _safe_pagerank(graph: nx.DiGraph) -> Dict[str, float]:
    if graph.number_of_nodes() == 0:
        return {}
    return {str(node): float(score) for node, score in nx.pagerank(graph).items()}


def _safe_betweenness(graph: nx.DiGraph) -> Dict[str, float]:
    if graph.number_of_nodes() == 0:
        return {}
    return {str(node): float(score) for node, score in nx.betweenness_centrality(graph).items()}


def _safe_weighted_eigenvector(graph: nx.DiGraph, max_iter: int = 1000, tol: float = 1e-6) -> Dict[str, float]:
    """Directed weighted eigenvector centrality via power iteration on incoming adjacency.

    Each node's score is the normalised weighted sum of its predecessors' scores -
    matching the algorithm used in the React front-end
    (computeDirectedWeightedEigenvectorCentrality in dashboardData.js).
    Edge weight equals the number of parallel edges between the same pair; because
    the underlying DiGraph already deduplicates edges this is always 1, but the
    formula is kept general for correctness.
    """
    node_ids = [str(n) for n in graph.nodes]
    n = len(node_ids)
    if n == 0:
        return {}

    import math

    # Build incoming adjacency with weights (count of parallel edges).
    # DiGraph.in_edges returns unique edges; weight defaults to 1 when absent.
    incoming: Dict[str, List[tuple]] = {nid: [] for nid in node_ids}
    for src, tgt, data in graph.edges(data=True):
        w = float(data.get("weight", 1))
        incoming[str(tgt)].append((str(src), w))

    values = {nid: 1.0 / math.sqrt(n) for nid in node_ids}

    for _ in range(max_iter):
        next_v = {nid: 0.0 for nid in node_ids}
        for nid in node_ids:
            for pred, w in incoming[nid]:
                next_v[nid] += w * values.get(pred, 0.0)

        norm = math.sqrt(sum(v ** 2 for v in next_v.values()))
        if norm == 0:
            return {nid: 0.0 for nid in node_ids}

        delta = sum(abs(next_v[nid] / norm - values[nid]) for nid in node_ids)
        values = {nid: next_v[nid] / norm for nid in node_ids}
        if delta < n * tol:
            break

    return values


def _approach_labels() -> Dict[str, str]:
    return dict(DEPENDENCY_APPROACH_LABELS)


def _build_pairwise_comparisons(network_data: Dict[str, Any]) -> Dict[str, Any]:
    use_canonical_edges = bool(_canonical_dependency_edges(network_data))
    node_id_map = _canonical_node_ids(network_data) if use_canonical_edges else {}
    nodes_by_id = {
        node_id_map.get(str(node.get("id")), str(node.get("id"))): node
        for node in network_data.get("nodes", [])
        if node.get("id") is not None
    }
    approach_labels = _approach_labels()
    pairwise: Dict[str, Any] = {}

    for approach_key, approach_label in approach_labels.items():
        approach_links = _links_for_type(network_data, approach_key)
        approach_edge_keys = {
            (str(link.get("source")), str(link.get("target")))
            for link in approach_links
        }

        for baseline_key, baseline_label in approach_labels.items():
            baseline_links = _links_for_type(network_data, baseline_key)
            baseline_edge_keys = {
                (str(link.get("source")), str(link.get("target")))
                for link in baseline_links
            }
            overlap_keys = approach_edge_keys & baseline_edge_keys
            approach_only_keys = approach_edge_keys - baseline_edge_keys
            baseline_only_keys = baseline_edge_keys - approach_edge_keys
            baseline_total = len(baseline_edge_keys)

            def _edge_rows(keys: set[tuple[str, str]], status: str) -> List[Dict[str, Any]]:
                return [
                    {
                        "source": source,
                        "target": target,
                        "source_title": nodes_by_id.get(source, {}).get("title"),
                        "target_title": nodes_by_id.get(target, {}).get("title"),
                        "status": status,
                    }
                    for source, target in sorted(keys, key=lambda item: (
                        int(item[0]) if item[0].isdigit() else float("inf"),
                        int(item[1]) if item[1].isdigit() else float("inf"),
                        item[0],
                        item[1],
                    ))
                ]

            comparison_key = f"{approach_key}__vs__{baseline_key}"
            pairwise[comparison_key] = {
                "approach": approach_key,
                "approach_label": approach_label,
                "baseline": baseline_key,
                "baseline_label": baseline_label,
                "summary": {
                    "approach_only": len(approach_only_keys),
                    "overlap": len(overlap_keys),
                    "baseline_only": len(baseline_only_keys),
                    "approach_total": len(approach_edge_keys),
                    "baseline_total": baseline_total,
                    "union_total": len(approach_edge_keys | baseline_edge_keys),
                    "hit_rate": float(len(overlap_keys) / baseline_total) if baseline_total else 0.0,
                    "missed_rate": float(len(baseline_only_keys) / baseline_total) if baseline_total else 0.0,
                },
                "edges": (
                    _edge_rows(overlap_keys, "overlap")
                    + _edge_rows(approach_only_keys, "approach_only")
                    + _edge_rows(baseline_only_keys, "baseline_only")
                ),
            }

    return pairwise


def extract_dependency_metrics(network_data: Dict[str, Any]) -> Dict[str, Any]:
    approaches = _approach_labels()
    by_approach: Dict[str, Dict[str, Any]] = {}

    for approach_key in DEPENDENCY_APPROACH_ORDER:
        approach_label = approaches[approach_key]
        graph = build_graph(network_data, link_type=approach_key)
        cycles = find_circular_dependencies(network_data, link_type=approach_key)
        betweenness = _safe_betweenness(graph)
        pagerank = _safe_pagerank(graph)
        weighted_eigenvector = _safe_weighted_eigenvector(graph)

        per_bip = sorted(
            [
                {
                    "id": str(node),
                    "title": graph.nodes[node].get("title"),
                    "in_degree": int(graph.in_degree(node)),
                    "out_degree": int(graph.out_degree(node)),
                    "betweenness": float(betweenness.get(str(node), 0.0)),
                    "pagerank": float(pagerank.get(str(node), 0.0)),
                    "weighted_eigenvector": float(weighted_eigenvector.get(str(node), 0.0)),
                }
                for node in graph.nodes
            ],
            key=lambda row: (int(row["id"]) if str(row["id"]).isdigit() else float("inf"), str(row["id"])),
        )

        by_approach[approach_key] = {
            "label": approach_label,
            "summary": {
                "node_count": int(graph.number_of_nodes()),
                "edge_count": int(graph.number_of_edges()),
                "isolated_node_count": int(len(list(nx.isolates(graph)))),
                "circular_dependency_count": int(len(cycles)),
                "density": float(nx.density(graph)) if graph.number_of_nodes() > 1 else 0.0,
            },
            "per_bip": per_bip,
        }

    return {
        "by_approach": by_approach,
        "pairwise_comparisons": _build_pairwise_comparisons(network_data),
    }
