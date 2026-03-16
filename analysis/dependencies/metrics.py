from typing import Any, Dict, Iterable, List

import networkx as nx


def build_graph(network_data: Dict[str, Any], link_type: str = "references") -> nx.DiGraph:
    graph = nx.DiGraph()

    for node in network_data.get("nodes", []):
        graph.add_node(
            str(node["id"]),
            group=node.get("group"),
            compliance_score=node.get("compliance_score", 0),
        )

    for link in network_data.get("links", {}).get(link_type, []):
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


def find_circular_dependencies(network_data: Dict[str, Any], link_type: str = "references") -> List[List[str]]:
    graph = build_graph(network_data, link_type=link_type)
    return [list(cycle) for cycle in nx.simple_cycles(graph)]
