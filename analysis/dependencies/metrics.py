from typing import Any, Dict, Iterable, List

import networkx as nx


def _links_for_type(network_data: Dict[str, Any], link_type: str) -> List[Dict[str, Any]]:
    links = network_data.get("links", {})
    explicit = links.get("explicit_dependencies", {})

    if link_type in {"requires", "replaces", "superseded_by"}:
        return explicit.get(link_type, [])

    if link_type == "explicit_dependencies":
        seen = set()
        merged: List[Dict[str, Any]] = []
        for subtype in ("requires", "replaces", "superseded_by"):
            for link in explicit.get(subtype, []):
                key = (str(link.get("source")), str(link.get("target")))
                if key in seen:
                    continue
                seen.add(key)
                merged.append(link)
        return merged

    return links.get(link_type, [])


def build_graph(network_data: Dict[str, Any], link_type: str = "explicit_references") -> nx.DiGraph:
    graph = nx.DiGraph()

    for node in network_data.get("nodes", []):
        graph.add_node(
            str(node["id"]),
            title=node.get("title"),
            layer=node.get("layer"),
            compliance_score=node.get("compliance_score", 0),
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


def find_circular_dependencies(network_data: Dict[str, Any], link_type: str = "explicit_references") -> List[List[str]]:
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


def extract_dependency_metrics(network_data: Dict[str, Any]) -> Dict[str, Any]:
    approaches = {
        "explicit_dependencies": "Explicit Dependencies",
        "explicit_references": "Explicit References",
        "implicit_dependencies": "Implicit Dependencies",
    }
    by_approach: Dict[str, Dict[str, Any]] = {}

    for approach_key, approach_label in approaches.items():
        graph = build_graph(network_data, link_type=approach_key)
        cycles = find_circular_dependencies(network_data, link_type=approach_key)
        betweenness = _safe_betweenness(graph)
        pagerank = _safe_pagerank(graph)

        per_bip = sorted(
            [
                {
                    "id": str(node),
                    "title": graph.nodes[node].get("title"),
                    "in_degree": int(graph.in_degree(node)),
                    "out_degree": int(graph.out_degree(node)),
                    "betweenness": float(betweenness.get(str(node), 0.0)),
                    "pagerank": float(pagerank.get(str(node), 0.0)),
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

    return {"by_approach": by_approach}
