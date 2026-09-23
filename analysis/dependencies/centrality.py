from collections.abc import Iterable, Sequence
from itertools import combinations
from typing import Any

from analysis.dependencies.constants import (
    DEPENDENCY_APPROACH_SHORT_LABELS,
    DEPENDENCY_PAIRWISE_COMPARISON_ORDER,
)

CENTRALITY_METRICS: tuple[tuple[str, str], ...] = (
    ("in_degree", "In-Degree"),
    ("weighted_eigenvector", "Weighted Eigenvector"),
    ("pagerank", "PageRank"),
    ("betweenness", "Betweenness"),
)
CENTRALITY_TOP_N = 5


def _graph_key_sort_key(value: str) -> tuple[str, int, str]:
    source_slug, separator, proposal_id = value.partition(":")
    if separator and proposal_id.isdigit():
        return source_slug, int(proposal_id), ""
    if not separator and value.isdigit():
        return "", int(value), ""
    return source_slug if separator else "", 0, proposal_id if separator else value


def _average_descending_ranks(values: Sequence[float]) -> tuple[list[float], int]:
    """Return average ranks and Kendall's tie-correction term."""
    indexed = sorted(enumerate(values), key=lambda item: (-item[1], item[0]))
    ranks = [0.0] * len(values)
    tie_correction = 0
    start = 0
    while start < len(indexed):
        end = start + 1
        while end < len(indexed) and indexed[end][1] == indexed[start][1]:
            end += 1
        average_rank = ((start + 1) + end) / 2
        for original_index, _value in indexed[start:end]:
            ranks[original_index] = average_rank
        tie_size = end - start
        tie_correction += tie_size**3 - tie_size
        start = end
    return ranks, tie_correction


def kendalls_w(rankings: Sequence[Sequence[float]]) -> float | None:
    """Compute tie-corrected Kendall's coefficient of concordance.

    Each inner sequence contains scores for the same ordered set of items;
    larger scores receive better ranks. ``None`` denotes an undefined result,
    for example when every ranking assigns every item the same score.
    """
    if len(rankings) < 2:
        return None
    item_count = len(rankings[0])
    if item_count < 2 or any(len(ranking) != item_count for ranking in rankings):
        return None

    ranked: list[list[float]] = []
    tie_correction = 0
    for ranking in rankings:
        ranks, ranking_ties = _average_descending_ranks(
            [float(value) for value in ranking]
        )
        ranked.append(ranks)
        tie_correction += ranking_ties

    ranking_count = len(ranked)
    expected_rank_sum = ranking_count * (item_count + 1) / 2
    rank_sums = [sum(ranking[index] for ranking in ranked) for index in range(item_count)]
    squared_deviation_sum = sum(
        (rank_sum - expected_rank_sum) ** 2 for rank_sum in rank_sums
    )
    denominator = (
        ranking_count**2 * (item_count**3 - item_count)
        - ranking_count * tie_correction
    )
    if denominator <= 0:
        return None

    value = 12 * squared_deviation_sum / denominator
    return min(1.0, max(0.0, float(value)))


def kendalls_tau_b(left: Sequence[float], right: Sequence[float]) -> float | None:
    """Compute Kendall's tau-b for two score sequences, correcting for ties."""
    if len(left) != len(right) or len(left) < 2:
        return None

    concordant = 0
    discordant = 0
    left_only_ties = 0
    right_only_ties = 0
    for first, second in combinations(range(len(left)), 2):
        left_delta = float(left[first]) - float(left[second])
        right_delta = float(right[first]) - float(right[second])
        if left_delta == 0 and right_delta == 0:
            continue
        if left_delta == 0:
            left_only_ties += 1
        elif right_delta == 0:
            right_only_ties += 1
        elif left_delta * right_delta > 0:
            concordant += 1
        else:
            discordant += 1

    left_comparable = concordant + discordant + left_only_ties
    right_comparable = concordant + discordant + right_only_ties
    denominator = (left_comparable * right_comparable) ** 0.5
    if denominator == 0:
        return None
    return float((concordant - discordant) / denominator)


def _rows_by_id(per_bip: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("id")): row
        for row in per_bip
        if str(row.get("id") or "").strip()
    }


def _global_highlight_indices(
    by_approach: dict[str, dict[str, Any]],
    approach_order: Sequence[str],
    metric_order: Sequence[str],
) -> dict[str, int]:
    """Assign stable color indexes to IPs recurring across Top-N cells."""
    cell_count: dict[str, int] = {}
    first_seen_order: dict[str, int] = {}
    for approach in approach_order:
        top_by_metric = by_approach[approach]["top_by_metric"]
        for metric in metric_order:
            for entry in top_by_metric[metric]:
                node_id = str(entry["id"])
                if node_id not in cell_count:
                    first_seen_order[node_id] = len(first_seen_order)
                cell_count[node_id] = cell_count.get(node_id, 0) + 1

    recurring_ids = sorted(
        (node_id for node_id, count in cell_count.items() if count > 1),
        key=lambda node_id: (-cell_count[node_id], first_seen_order[node_id]),
    )
    return {node_id: index for index, node_id in enumerate(recurring_ids)}


def build_centrality_comparison_payload(
    dependency_metrics: dict[str, Any],
    *,
    network_data: dict[str, Any] | None = None,
    top_n: int = CENTRALITY_TOP_N,
) -> dict[str, Any]:
    """Build the shared RQ3 payload from precomputed dependency metrics."""
    source_by_approach = dependency_metrics.get("by_approach") or {}
    approach_order = [
        approach
        for approach in DEPENDENCY_PAIRWISE_COMPARISON_ORDER
        if approach in source_by_approach
    ]
    metric_order = [metric for metric, _label in CENTRALITY_METRICS]
    metric_labels = dict(CENTRALITY_METRICS)
    approach_pairs = [
        {
            "key": f"{left}__{right}",
            "left_approach": left,
            "right_approach": right,
            "left_label": DEPENDENCY_APPROACH_SHORT_LABELS.get(left, left),
            "right_label": DEPENDENCY_APPROACH_SHORT_LABELS.get(right, right),
        }
        for left, right in combinations(approach_order, 2)
    ]
    rows_by_approach = {
        approach: _rows_by_id(source_by_approach[approach].get("per_bip") or [])
        for approach in approach_order
    }
    network_node_ids = {
        str(
            node.get("graph_key")
            or node.get("graphId")
            or node.get("graph_id")
            or node.get("id")
            or ""
        ).strip()
        for node in (network_data or {}).get("nodes", [])
        if isinstance(node, dict)
    }
    network_node_ids.discard("")
    node_ids = sorted(
        network_node_ids
        or {
            node_id
            for approach_rows in rows_by_approach.values()
            for node_id in approach_rows
        },
        key=_graph_key_sort_key,
    )
    def scores(
        approach: str, metric: str, selected_node_ids: Sequence[str]
    ) -> list[float]:
        approach_rows = rows_by_approach.get(approach, {})
        return [
            float(approach_rows.get(node_id, {}).get(metric, 0.0) or 0.0)
            for node_id in selected_node_ids
        ]

    by_approach: dict[str, dict[str, Any]] = {}
    for approach in approach_order:
        approach_rows = rows_by_approach[approach]
        top_by_metric: dict[str, list[dict[str, Any]]] = {}
        for metric in metric_order:
            ranked_rows = sorted(
                (
                    row
                    for node_id, row in approach_rows.items()
                    if node_id in node_ids
                ),
                key=lambda row: (
                    -float(row.get(metric, 0.0) or 0.0),
                    _graph_key_sort_key(str(row.get("id") or "")),
                ),
            )[:top_n]
            top_by_metric[metric] = [
                {
                    "id": str(row.get("id") or ""),
                    "title": str(row.get("title") or ""),
                    "value": row.get(metric, 0),
                    "rank": int(row.get(f"{metric}_rank", index)),
                }
                for index, row in enumerate(ranked_rows, start=1)
            ]

        by_approach[approach] = {
            "label": DEPENDENCY_APPROACH_SHORT_LABELS.get(approach, approach),
            "top_by_metric": top_by_metric,
        }

    top_scope_node_ids = sorted(
        {
            entry["id"]
            for approach in approach_order
            for metric in metric_order
            for entry in by_approach[approach]["top_by_metric"][metric]
        },
        key=_graph_key_sort_key,
    )

    def build_concordance_scope(
        scope_node_ids: Sequence[str],
    ) -> dict[str, list[dict[str, Any]]]:
        approach_concordance = []
        for metric in metric_order:
            selected_ids = list(scope_node_ids)
            approach_scores = {
                approach: scores(approach, metric, selected_ids)
                for approach in approach_order
            }
            approach_concordance.append(
                {
                    "metric": metric,
                    "label": metric_labels[metric],
                    "kendalls_w": kendalls_w(
                        [approach_scores[approach] for approach in approach_order]
                    ),
                    "pairwise_kendalls_tau_b": {
                        pair["key"]: kendalls_tau_b(
                            approach_scores[pair["left_approach"]],
                            approach_scores[pair["right_approach"]],
                        )
                        for pair in approach_pairs
                    },
                    "ranking_count": len(approach_order),
                    "item_count": len(selected_ids),
                }
            )

        measure_concordance = []
        for approach in approach_order:
            selected_ids = list(scope_node_ids)
            measure_concordance.append(
                {
                    "approach": approach,
                    "label": DEPENDENCY_APPROACH_SHORT_LABELS.get(
                        approach, approach
                    ),
                    "kendalls_w": kendalls_w(
                        [
                            scores(approach, metric, selected_ids)
                            for metric in metric_order
                        ]
                    ),
                    "ranking_count": len(metric_order),
                    "item_count": len(selected_ids),
                }
            )

        return {
            "across_approaches": approach_concordance,
            "across_measures": measure_concordance,
        }

    concordance = {
        "top": build_concordance_scope(top_scope_node_ids),
        "all": build_concordance_scope(node_ids),
    }
    scope_item_counts = {
        "top": len(top_scope_node_ids),
        "all": len(node_ids),
    }
    highlight_indices = _global_highlight_indices(
        by_approach, approach_order, metric_order
    )
    for approach in approach_order:
        for metric in metric_order:
            for entry in by_approach[approach]["top_by_metric"][metric]:
                entry["highlight_index"] = highlight_indices.get(entry["id"])

    return {
        "meta": {
            "schema_version": 3,
            "approach_order": approach_order,
            "approach_pairs": approach_pairs,
            "metric_order": metric_order,
            "metric_labels": metric_labels,
            "top_n": top_n,
            "node_count": len(node_ids),
            "scope_item_counts": scope_item_counts,
            "llm_model": str(dependency_metrics.get("llm_model") or ""),
            "highlight_count": len(highlight_indices),
        },
        "by_approach": by_approach,
        "concordance": concordance,
    }
