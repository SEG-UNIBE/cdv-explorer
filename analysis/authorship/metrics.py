import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple

import networkx as nx


def _clean_author_name(author: str) -> str:
    return re.split(r"<", author)[0].strip()


def _iter_authors(nodes: Iterable[Dict[str, Any]]) -> Iterable[str]:
    for node in nodes:
        authors = node.get("author")
        if isinstance(authors, list):
            for author in authors:
                cleaned = _clean_author_name(str(author))
                if cleaned:
                    yield cleaned


def _extract_year(date_text: str | None) -> int | None:
    if not date_text:
        return None
    try:
        return datetime.strptime(date_text, "%Y-%m-%d").year
    except ValueError:
        return None


def build_collaboration_network(nodes: List[Dict[str, Any]]) -> nx.Graph:
    graph = nx.Graph()
    edge_weights: Dict[Tuple[str, str], int] = defaultdict(int)

    for node in nodes:
        authors = node.get("author")
        if not isinstance(authors, list):
            continue

        cleaned = [_clean_author_name(str(a)) for a in authors if _clean_author_name(str(a))]
        if len(cleaned) < 2:
            continue

        for i in range(len(cleaned)):
            for j in range(i + 1, len(cleaned)):
                a, b = sorted([cleaned[i], cleaned[j]])
                edge_weights[(a, b)] += 1

    for (a, b), w in edge_weights.items():
        graph.add_edge(a, b, weight=w)

    return graph


def extract_authorship_metrics(nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    author_counts = Counter(_iter_authors(nodes))
    top_authors = [{"author": name, "count": count} for name, count in author_counts.most_common(15)]

    years = []
    for node in nodes:
        year = _extract_year(node.get("created"))
        if year is not None:
            years.append(year)

    year_counts = Counter(years)
    bips_per_year = [{"year": y, "count": year_counts[y]} for y in sorted(year_counts.keys())]

    contribution_distribution = Counter(author_counts.values())
    author_histogram = [
        {"bips_written": k, "authors": contribution_distribution[k]}
        for k in sorted(contribution_distribution.keys())
    ]

    total_proposals = len({str(n.get("id")) for n in nodes if n.get("id") is not None})
    top_10 = author_counts.most_common(10)
    proposals_by_top_10 = sum(count for _, count in top_10)
    top_10_share = (proposals_by_top_10 / total_proposals * 100.0) if total_proposals else 0.0

    collab_graph = build_collaboration_network(nodes)
    collab_nodes = [{"id": n, "degree": int(collab_graph.degree(n))} for n in collab_graph.nodes()]
    collab_edges = [
        {"source": u, "target": v, "weight": int(d.get("weight", 1))}
        for u, v, d in collab_graph.edges(data=True)
    ]

    return {
        "author_count": len(author_counts),
        "top_authors": top_authors,
        "proposals_per_year": bips_per_year,
        "author_contribution_histogram": author_histogram,
        "top_10_share": {
            "total_proposals": total_proposals,
            "proposals_by_top_10_authors": proposals_by_top_10,
            "percentage": round(top_10_share, 2),
        },
        "collaboration_network": {
            "nodes": collab_nodes,
            "edges": collab_edges,
        },
    }


def compute_centrality_scores(graph: nx.Graph) -> List[Dict[str, Any]]:
    degree = nx.degree_centrality(graph)
    betweenness = nx.betweenness_centrality(graph)
    closeness = nx.closeness_centrality(graph)

    try:
        eigenvector = nx.eigenvector_centrality(graph, max_iter=1000)
    except nx.NetworkXException:
        eigenvector = {node: 0.0 for node in graph.nodes()}

    centrality_data: List[Dict[str, Any]] = []
    for node in graph.nodes():
        centrality_data.append(
            {
                "author": node,
                "degree": float(degree.get(node, 0.0)),
                "betweenness": float(betweenness.get(node, 0.0)),
                "closeness": float(closeness.get(node, 0.0)),
                "eigenvector": float(eigenvector.get(node, 0.0)),
            }
        )

    return sorted(centrality_data, key=lambda x: x["eigenvector"], reverse=True)


def prepare_authorship_payload(network_data: Dict[str, Any]) -> Dict[str, Any]:
    nodes = network_data.get("nodes", [])
    authorship = extract_authorship_metrics(nodes)

    return {
        "meta": {
            "node_count": len(nodes),
            "author_count": authorship["author_count"],
            "generated_metrics": [
                "top_authors",
                "bips_per_year",
                "author_contribution_histogram",
                "top_10_share",
                "collaboration_network",
                "collaboration_centrality",
            ],
        },
        "top_authors": authorship["top_authors"],
        "bips_per_year": authorship["proposals_per_year"],
        "author_contribution_histogram": authorship["author_contribution_histogram"],
        "top_10_share": {
            "total_bips": authorship["top_10_share"]["total_proposals"],
            "bips_by_top_10_authors": authorship["top_10_share"]["proposals_by_top_10_authors"],
            "percentage": authorship["top_10_share"]["percentage"],
        },
        "collaboration_network": authorship["collaboration_network"],
        "collaboration_centrality": compute_centrality_scores(
            build_collaboration_network(nodes)
        ),
    }
