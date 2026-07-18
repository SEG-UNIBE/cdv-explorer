import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

import networkx as nx

AUTHOR_RANK_FIELDS = (
    "rawDegree",
    "weightedDegree",
    "weightedEigenvector",
    "betweenness",
)


def _clean_author_name(author: str, aliases: Mapping[str, str] | None = None) -> str:
    cleaned = re.split(r"<", author)[0].strip()
    if aliases and cleaned:
        cleaned = str(aliases.get(cleaned, cleaned))
    return cleaned


def _node_author_names(
    node: dict[str, Any],
    field: str,
    aliases: Mapping[str, str] | None = None,
) -> list[str]:
    """Cleaned, alias-resolved, de-duplicated names for one node's field."""
    authors = node.get(field)
    if not isinstance(authors, list):
        return []
    seen: set[str] = set()
    names: list[str] = []
    for author in authors:
        cleaned = _clean_author_name(str(author), aliases)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            names.append(cleaned)
    return names


def _iter_authors(
    nodes: Iterable[dict[str, Any]],
    field: str = "author",
    aliases: Mapping[str, str] | None = None,
) -> Iterable[str]:
    for node in nodes:
        yield from _node_author_names(node, field, aliases)


def _extract_year(date_text: str | None) -> int | None:
    if not date_text:
        return None
    try:
        return datetime.strptime(date_text, "%Y-%m-%d").year
    except ValueError:
        return None


def build_collaboration_network(
    nodes: list[dict[str, Any]],
    field: str = "author",
    aliases: Mapping[str, str] | None = None,
) -> nx.Graph:
    graph = nx.Graph()
    edge_weights: dict[tuple[str, str], int] = defaultdict(int)

    for author in _iter_authors(nodes, field, aliases):
        graph.add_node(author)

    for node in nodes:
        cleaned = _node_author_names(node, field, aliases)
        if len(cleaned) < 2:
            continue

        for i in range(len(cleaned)):
            for j in range(i + 1, len(cleaned)):
                a, b = sorted([cleaned[i], cleaned[j]])
                edge_weights[(a, b)] += 1

    for (a, b), w in edge_weights.items():
        graph.add_edge(a, b, weight=w)

    return graph


def extract_authorship_metrics(
    nodes: list[dict[str, Any]],
    field: str = "author",
    aliases: Mapping[str, str] | None = None,
    include_network: bool = True,
) -> dict[str, Any]:
    author_counts = Counter(_iter_authors(nodes, field, aliases))
    top_authors = [
        {"author": name, "count": count}
        for name, count in author_counts.most_common(15)
    ]

    years = []
    for node in nodes:
        year = _extract_year(node.get("created"))
        if year is not None:
            years.append(year)

    year_counts = Counter(years)
    bips_per_year = [
        {"year": y, "count": year_counts[y]} for y in sorted(year_counts.keys())
    ]

    contribution_distribution = Counter(author_counts.values())
    author_histogram = [
        {"bips_written": k, "authors": contribution_distribution[k]}
        for k in sorted(contribution_distribution.keys())
    ]

    bip_author_counts = Counter()
    for node in nodes:
        bip_author_counts[len(_node_author_names(node, field, aliases))] += 1
    bip_author_count_histogram = [
        {"author_count": k, "bip_count": bip_author_counts[k]}
        for k in sorted(bip_author_counts.keys())
        if k > 0
    ]

    total_proposals = len({str(n.get("id")) for n in nodes if n.get("id") is not None})
    top_10 = author_counts.most_common(10)
    proposals_by_top_10 = sum(count for _, count in top_10)
    top_10_share = (
        (proposals_by_top_10 / total_proposals * 100.0) if total_proposals else 0.0
    )

    metrics = {
        "author_count": len(author_counts),
        "top_authors": top_authors,
        "proposals_per_year": bips_per_year,
        "author_contribution_histogram": author_histogram,
        "bip_author_count_histogram": bip_author_count_histogram,
        "top_10_share": {
            "total_proposals": total_proposals,
            "proposals_by_top_10_authors": proposals_by_top_10,
            "percentage": round(top_10_share, 2),
        },
    }

    # The pairwise co-authorship network is near-clique-dense for the
    # contributors field (registry files like SLIP-44 have 1000+ committers),
    # so callers that only need the count metrics skip it entirely.
    if include_network:
        collab_graph = build_collaboration_network(nodes, field, aliases)
        metrics["collaboration_network"] = {
            "nodes": [
                {"id": n, "degree": int(collab_graph.degree(n))}
                for n in collab_graph.nodes()
            ],
            "edges": [
                {"source": u, "target": v, "weight": int(d.get("weight", 1))}
                for u, v, d in collab_graph.edges(data=True)
            ],
        }

    return metrics


def compute_centrality_scores(graph: nx.Graph) -> list[dict[str, Any]]:
    degree = nx.degree_centrality(graph)
    betweenness = nx.betweenness_centrality(graph)
    closeness = nx.closeness_centrality(graph)

    try:
        eigenvector = nx.eigenvector_centrality(graph, max_iter=1000)
    except nx.NetworkXException:
        eigenvector = {node: 0.0 for node in graph.nodes()}

    centrality_data: list[dict[str, Any]] = []
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


def _compute_weighted_eigenvector(
    node_ids: list[str],
    adjacency: dict[str, list[dict[str, Any]]],
    max_iterations: int = 1000,
    tolerance: float = 1e-6,
) -> dict[str, float]:
    author_ids = list(
        dict.fromkeys(str(node_id) for node_id in node_ids if str(node_id))
    )
    node_count = len(author_ids)
    if node_count == 0:
        return {}

    values = {author_id: 1 / math.sqrt(node_count) for author_id in author_ids}

    for _ in range(max_iterations):
        next_values = {author_id: 0.0 for author_id in author_ids}

        for author_id in author_ids:
            for neighbor in adjacency.get(author_id, []):
                neighbor_id = str(neighbor.get("id") or "")
                weight = float(neighbor.get("weight") or 0.0)
                next_values[author_id] += weight * values.get(neighbor_id, 0.0)

        norm = math.sqrt(sum(value**2 for value in next_values.values()))
        if norm == 0:
            return {author_id: 0.0 for author_id in author_ids}

        delta = 0.0
        for author_id in author_ids:
            normalized_value = next_values[author_id] / norm
            delta += abs(normalized_value - values.get(author_id, 0.0))
            values[author_id] = normalized_value

        if delta < node_count * tolerance:
            break

    return values


def _compute_weighted_pagerank(
    node_ids: list[str],
    adjacency: dict[str, list[dict[str, Any]]],
    damping: float = 0.85,
    max_iterations: int = 1000,
    tolerance: float = 1e-6,
) -> dict[str, float]:
    author_ids = list(
        dict.fromkeys(str(node_id) for node_id in node_ids if str(node_id))
    )
    node_count = len(author_ids)
    if node_count == 0:
        return {}

    ranks = {author_id: 1 / node_count for author_id in author_ids}
    outgoing_weight_by_author = {
        author_id: sum(
            float(neighbor.get("weight") or 0.0)
            for neighbor in adjacency.get(author_id, [])
        )
        for author_id in author_ids
    }

    for _ in range(max_iterations):
        dangling_mass = sum(
            ranks.get(author_id, 0.0)
            for author_id in author_ids
            if outgoing_weight_by_author.get(author_id, 0.0) == 0.0
        )
        base_score = ((1 - damping) + (damping * dangling_mass)) / node_count
        next_ranks = {author_id: base_score for author_id in author_ids}

        for author_id in author_ids:
            neighbors = adjacency.get(author_id, [])
            total_outgoing_weight = outgoing_weight_by_author.get(author_id, 0.0)
            if total_outgoing_weight == 0.0:
                continue
            for neighbor in neighbors:
                neighbor_id = str(neighbor.get("id") or "")
                weight = float(neighbor.get("weight") or 0.0)
                contribution = (
                    damping
                    * ranks.get(author_id, 0.0)
                    * (weight / total_outgoing_weight)
                )
                next_ranks[neighbor_id] = (
                    next_ranks.get(neighbor_id, base_score) + contribution
                )

        delta = 0.0
        for author_id in author_ids:
            delta += abs(next_ranks.get(author_id, 0.0) - ranks.get(author_id, 0.0))
            ranks[author_id] = next_ranks.get(author_id, 0.0)
        if delta < tolerance:
            break

    return ranks


def _build_true_components(
    node_ids: list[str], adjacency: dict[str, list[dict[str, Any]]]
) -> list[list[str]]:
    visited = set()
    components: list[list[str]] = []

    for node_id in node_ids:
        if node_id in visited:
            continue

        queue = [node_id]
        members: list[str] = []
        visited.add(node_id)
        head = 0

        while head < len(queue):
            current = queue[head]
            head += 1
            members.append(current)

            for neighbor in adjacency.get(current, []):
                neighbor_id = str(neighbor.get("id") or "")
                if not neighbor_id or neighbor_id in visited:
                    continue
                visited.add(neighbor_id)
                queue.append(neighbor_id)

        components.append(members)

    return sorted(components, key=len, reverse=True)


def _build_display_components(
    node_ids: list[str], adjacency: dict[str, list[dict[str, Any]]]
) -> list[list[str]]:
    isolated_ids: list[str] = []
    components: list[list[str]] = []

    for members in _build_true_components(node_ids, adjacency):
        if len(members) == 1:
            isolated_ids.append(members[0])
        else:
            components.append(members)

    if isolated_ids:
        components.append(sorted(isolated_ids))

    return components


def _rank_author_rows(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    sorted_rows = sorted(rows, key=lambda row: float(row.get(field, 0.0)), reverse=True)
    ranks: dict[str, int] = {}
    current_rank = 0
    previous_value = None

    for index, row in enumerate(sorted_rows, start=1):
        value = float(row.get(field, 0.0))
        if previous_value is None or value != previous_value:
            current_rank = index
            previous_value = value
        ranks[str(row.get("author"))] = current_rank

    return ranks


def build_collaboration_metrics_payload(
    collaboration_network: dict[str, Any],
    collaboration_centrality: list[dict[str, Any]],
) -> dict[str, Any]:
    raw_nodes = (
        collaboration_network.get("nodes", [])
        if isinstance(collaboration_network, dict)
        else []
    )
    raw_edges = (
        collaboration_network.get("edges", [])
        if isinstance(collaboration_network, dict)
        else []
    )
    node_ids = [str(node.get("id")) for node in raw_nodes if node.get("id") is not None]
    adjacency: dict[str, list[dict[str, Any]]] = {node_id: [] for node_id in node_ids}
    weighted_degree_by_author: dict[str, float] = {node_id: 0.0 for node_id in node_ids}

    for edge in raw_edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        weight = float(edge.get("weight") or 1.0)
        if not source or not target:
            continue
        adjacency.setdefault(source, [])
        adjacency.setdefault(target, [])
        weighted_degree_by_author.setdefault(source, 0.0)
        weighted_degree_by_author.setdefault(target, 0.0)
        adjacency[source].append({"id": target, "weight": weight})
        adjacency[target].append({"id": source, "weight": weight})
        weighted_degree_by_author[source] += weight
        weighted_degree_by_author[target] += weight

    true_components = _build_true_components(node_ids, adjacency)
    display_components = _build_display_components(node_ids, adjacency)
    cluster_meta_by_author: dict[str, dict[str, int | None]] = {}
    for index, members in enumerate(display_components, start=1):
        for author in members:
            cluster_meta_by_author[author] = {
                "clusterId": index,
                "clusterSize": len(members),
            }

    centrality_by_author = {
        str(entry.get("author")): entry
        for entry in (collaboration_centrality or [])
        if entry.get("author") is not None
    }
    weighted_eigenvector_by_author = _compute_weighted_eigenvector(node_ids, adjacency)
    pagerank_by_author = _compute_weighted_pagerank(node_ids, adjacency)

    degree_rows = sorted(
        [
            {
                "author": author,
                "clusterId": cluster_meta_by_author.get(author, {}).get("clusterId"),
                "clusterSize": cluster_meta_by_author.get(author, {}).get(
                    "clusterSize", 1
                ),
                "rawDegree": int(len(adjacency.get(author, []))),
                "weightedDegree": float(weighted_degree_by_author.get(author, 0.0)),
                "betweenness": float(
                    centrality_by_author.get(author, {}).get("betweenness", 0.0)
                ),
                "normalizedDegree": float(
                    centrality_by_author.get(author, {}).get("degree", 0.0)
                ),
                "pagerank": float(pagerank_by_author.get(author, 0.0)),
            }
            for author in node_ids
        ],
        key=lambda row: (-int(row["rawDegree"]), str(row["author"])),
    )

    eigenvector_by_author = {
        str(author): {
            "eigenvector": float(
                centrality_by_author.get(author, {}).get("eigenvector", 0.0)
            ),
            "weightedEigenvector": float(
                weighted_eigenvector_by_author.get(author, 0.0)
            ),
        }
        for author in node_ids
    }

    metrics_rows = []
    for row in degree_rows:
        eigenvector_row = eigenvector_by_author.get(str(row["author"]), {})
        metrics_rows.append(
            {
                **row,
                "eigenvector": float(eigenvector_row.get("eigenvector", 0.0)),
                "weightedEigenvector": float(
                    eigenvector_row.get("weightedEigenvector", 0.0)
                ),
            }
        )

    rank_maps = {
        field: _rank_author_rows(metrics_rows, field) for field in AUTHOR_RANK_FIELDS
    }
    for row in metrics_rows:
        author = str(row.get("author"))
        for field in AUTHOR_RANK_FIELDS:
            row[f"{field}Rank"] = int(rank_maps[field].get(author, 0))

    cluster_size_distribution = [
        {
            "clusterSize": int(cluster_size),
            "clusterCount": int(cluster_count),
            "authorCount": int(cluster_size) * int(cluster_count),
        }
        for cluster_size, cluster_count in sorted(
            Counter(len(members) for members in true_components).items(),
            key=lambda item: item[0],
        )
    ]

    degree_distribution = [
        {
            "degree": int(degree),
            "authorCount": int(author_count),
        }
        for degree, author_count in sorted(
            Counter(int(row.get("rawDegree", 0)) for row in degree_rows).items(),
            key=lambda item: item[0],
        )
    ]

    node_count = len(node_ids)
    edge_count = len(raw_edges)
    isolated_author_count = sum(
        1 for row in degree_rows if int(row.get("rawDegree", 0)) == 0
    )
    cluster_count = len(display_components)
    density = (
        float(edge_count / ((node_count * (node_count - 1)) / 2))
        if node_count > 1
        else 0.0
    )
    largest_cluster_size = len(true_components[0]) if true_components else 0
    true_cluster_count = len(true_components)
    solo_cluster_count = next(
        (
            entry["clusterCount"]
            for entry in cluster_size_distribution
            if entry["clusterSize"] == 1
        ),
        0,
    )
    pair_cluster_count = next(
        (
            entry["clusterCount"]
            for entry in cluster_size_distribution
            if entry["clusterSize"] == 2
        ),
        0,
    )
    single_coauthor_count = next(
        (entry["authorCount"] for entry in degree_distribution if entry["degree"] == 1),
        0,
    )
    low_degree_author_count = sum(
        entry["authorCount"] for entry in degree_distribution if entry["degree"] <= 1
    )
    average_degree = (
        float(sum(int(row.get("rawDegree", 0)) for row in degree_rows) / node_count)
        if node_count > 0
        else 0.0
    )
    max_degree = int(degree_distribution[-1]["degree"]) if degree_distribution else 0

    return {
        "summary": {
            "nodeCount": node_count,
            "edgeCount": edge_count,
            "isolatedAuthorCount": isolated_author_count,
            "clusterCount": cluster_count,
            "density": density,
            "trueClusterCount": true_cluster_count,
            "soloClusterCount": solo_cluster_count,
            "pairClusterCount": pair_cluster_count,
            "largestClusterSize": largest_cluster_size,
            "singleCoauthorCount": single_coauthor_count,
            "lowDegreeAuthorCount": low_degree_author_count,
            "averageDegree": average_degree,
            "maxDegree": max_degree,
        },
        "metricsRows": metrics_rows,
        "clusterSizeDistribution": cluster_size_distribution,
        "degreeDistribution": degree_distribution,
    }


def build_contributor_coverage(
    nodes: list[dict[str, Any]],
    aliases: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Compare declared authorship with actual git activity on proposal files."""
    declared = set(_iter_authors(nodes, "author", aliases))
    contributors = set(_iter_authors(nodes, "contributors", aliases))
    also_declared = len(declared & contributors)

    proposals_with_git_data = 0
    proposals_with_uncredited = 0
    for node in nodes:
        node_contributors = set(_node_author_names(node, "contributors", aliases))
        if not node_contributors:
            continue
        proposals_with_git_data += 1
        node_declared = set(_node_author_names(node, "author", aliases))
        if node_contributors - node_declared:
            proposals_with_uncredited += 1

    return {
        "contributor_count": len(contributors),
        "declared_author_count": len(declared),
        "contributors_also_declared": also_declared,
        "contributors_never_declared": len(contributors) - also_declared,
        "proposals_with_git_data": proposals_with_git_data,
        "proposals_with_uncredited": proposals_with_uncredited,
    }


def _graph_from_collaboration_network(
    collaboration_network: dict[str, Any],
) -> nx.Graph:
    """Rebuild the nx graph from an already-serialized collaboration network.

    Much cheaper than build_collaboration_network, which re-derives the edge
    cliques from every node's author list — expensive for the dense
    contributor-basis graph.
    """
    graph = nx.Graph()
    for node in collaboration_network.get("nodes", []):
        if node.get("id") is not None:
            graph.add_node(str(node["id"]))
    for edge in collaboration_network.get("edges", []):
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source and target:
            graph.add_edge(source, target, weight=edge.get("weight", 1))
    return graph


def prepare_authorship_payload(
    network_data: dict[str, Any],
    field: str = "author",
    aliases: Mapping[str, str] | None = None,
    authorship: dict[str, Any] | None = None,
    contributor_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the frontend authorship payload.

    Pass precomputed `authorship` metrics (from extract_authorship_metrics with
    the same field/aliases) to avoid re-extracting them — the pipeline computes
    them anyway for the metrics artifacts. `contributor_metrics` (the
    field="contributors" extraction) feeds the small git-contributor tile block;
    its dense collaboration network is deliberately NOT included.
    """
    nodes = network_data.get("nodes", [])
    if authorship is None:
        authorship = extract_authorship_metrics(nodes, field=field, aliases=aliases)
    collaboration_network = authorship["collaboration_network"]
    collaboration_centrality = compute_centrality_scores(
        _graph_from_collaboration_network(collaboration_network)
    )
    collaboration_metrics = build_collaboration_metrics_payload(
        collaboration_network,
        collaboration_centrality,
    )

    return {
        "meta": {
            "node_count": len(nodes),
            "author_count": authorship["author_count"],
            # Which node field the metrics were computed from ("author" =
            # declared authors, "contributors" = everyone who committed to the
            # file) and the alias map applied, so the frontend can resolve raw
            # node names to the same canonical identities.
            "author_field": field,
            "author_aliases": dict(aliases or {}),
            "generated_metrics": [
                "top_authors",
                "bips_per_year",
                "author_contribution_histogram",
                "top_10_share",
                "collaboration_network",
                "collaboration_centrality",
                "collaboration_metrics_summary",
                "collaboration_metrics_rows",
                "collaboration_cluster_size_distribution",
                "collaboration_degree_distribution",
            ],
        },
        "top_authors": authorship["top_authors"],
        "bips_per_year": authorship["proposals_per_year"],
        "author_contribution_histogram": authorship["author_contribution_histogram"],
        "bip_author_count_histogram": authorship["bip_author_count_histogram"],
        "top_10_share": {
            "total_bips": authorship["top_10_share"]["total_proposals"],
            "bips_by_top_10_authors": authorship["top_10_share"][
                "proposals_by_top_10_authors"
            ],
            "percentage": authorship["top_10_share"]["percentage"],
        },
        # Git-contributor tiles: only the small aggregates, never the dense
        # contributor collaboration graph (too large to ship or render).
        "contributors": (
            {
                "top_contributors": contributor_metrics.get("top_authors", []),
                "contribution_histogram": contributor_metrics.get(
                    "author_contribution_histogram", []
                ),
                "per_proposal_histogram": contributor_metrics.get(
                    "bip_author_count_histogram", []
                ),
                "coverage": build_contributor_coverage(nodes, aliases),
            }
            if contributor_metrics is not None
            else None
        ),
        "collaboration_network": collaboration_network,
        "collaboration_centrality": collaboration_centrality,
        "collaboration_metrics_summary": collaboration_metrics["summary"],
        "collaboration_metrics_rows": collaboration_metrics["metricsRows"],
        "collaboration_cluster_size_distribution": collaboration_metrics[
            "clusterSizeDistribution"
        ],
        "collaboration_degree_distribution": collaboration_metrics[
            "degreeDistribution"
        ],
    }
