import pytest

from analysis.dependencies.centrality import (
    build_centrality_comparison_payload,
    kendalls_tau_b,
    kendalls_w,
)
from analysis.dependencies.constants import (
    BODY_EXTRACTED_LLM,
    BODY_EXTRACTED_REGEX,
    PREAMBLE_EXTRACTED,
)


def test_kendalls_w_handles_agreement_disagreement_and_ties() -> None:
    assert kendalls_w([[4, 3, 2, 1], [40, 30, 20, 10]]) == pytest.approx(1.0)
    assert kendalls_w([[4, 3, 2, 1], [1, 2, 3, 4]]) == pytest.approx(0.0)
    assert kendalls_w([[2, 2, 1], [8, 8, 3]]) == pytest.approx(1.0)
    assert kendalls_w([[1, 1], [2, 2]]) is None


def test_kendalls_tau_b_handles_agreement_disagreement_and_ties() -> None:
    assert kendalls_tau_b([4, 3, 2, 1], [40, 30, 20, 10]) == pytest.approx(1.0)
    assert kendalls_tau_b([4, 3, 2, 1], [10, 20, 30, 40]) == pytest.approx(-1.0)
    assert kendalls_tau_b([2, 2, 1], [8, 8, 3]) == pytest.approx(1.0)
    assert kendalls_tau_b([1, 1], [2, 2]) is None


def test_build_centrality_comparison_payload_uses_all_nodes() -> None:
    approaches = [PREAMBLE_EXTRACTED, BODY_EXTRACTED_REGEX, BODY_EXTRACTED_LLM]
    rows = {
        PREAMBLE_EXTRACTED: [("bips:1", 3), ("bips:2", 2), ("bips:3", 0)],
        BODY_EXTRACTED_REGEX: [("bips:1", 30), ("bips:2", 20), ("bips:3", 0)],
        BODY_EXTRACTED_LLM: [
            ("slips:44", 100),
            ("bips:1", 4),
            ("bips:2", 1),
            ("bips:3", 0),
        ],
    }
    dependency_metrics = {
        "llm_model": "test-model",
        "by_approach": {
            approach: {
                "per_bip": [
                    {
                        "id": node_id,
                        "title": f"Proposal {node_id}",
                        "in_degree": value,
                        "in_degree_rank": index,
                        "weighted_eigenvector": value,
                        "weighted_eigenvector_rank": index,
                        "pagerank": value,
                        "pagerank_rank": index,
                        "betweenness": value,
                        "betweenness_rank": index,
                    }
                    for index, (node_id, value) in enumerate(rows[approach], start=1)
                ]
            }
            for approach in approaches
        },
    }

    payload = build_centrality_comparison_payload(
        dependency_metrics,
        network_data={
            "nodes": [
                {"id": "1", "graph_key": "bips:1"},
                {"id": "2", "graph_key": "bips:2"},
                {"id": "3", "graph_key": "bips:3"},
            ]
        },
        top_n=2,
    )

    assert payload["meta"]["node_count"] == 3
    assert payload["meta"]["top_n"] == 2
    assert payload["meta"]["llm_model"] == "test-model"
    assert [pair["key"] for pair in payload["meta"]["approach_pairs"]] == [
        f"{PREAMBLE_EXTRACTED}__{BODY_EXTRACTED_REGEX}",
        f"{PREAMBLE_EXTRACTED}__{BODY_EXTRACTED_LLM}",
        f"{BODY_EXTRACTED_REGEX}__{BODY_EXTRACTED_LLM}",
    ]
    assert payload["meta"]["highlight_count"] == 2
    assert [
        row["id"]
        for row in payload["by_approach"][PREAMBLE_EXTRACTED]["top_by_metric"][
            "in_degree"
        ]
    ] == ["bips:1", "bips:2"]
    assert [
        row["id"]
        for row in payload["by_approach"][BODY_EXTRACTED_LLM]["top_by_metric"][
            "in_degree"
        ]
    ] == ["bips:1", "bips:2"]
    assert set(payload["concordance"]) == {"top", "all"}
    assert len(payload["concordance"]["all"]["across_approaches"]) == 4
    assert len(payload["concordance"]["all"]["across_measures"]) == 3
    assert payload["concordance"]["all"]["across_approaches"][0][
        "kendalls_w"
    ] == pytest.approx(1.0)
    assert set(
        payload["concordance"]["all"]["across_approaches"][0][
            "pairwise_kendalls_tau_b"
        ]
    ) == {
        pair["key"] for pair in payload["meta"]["approach_pairs"]
    }
    assert payload["concordance"]["top"]["across_approaches"][0][
        "item_count"
    ] == 2
    assert payload["meta"]["scope_item_counts"]["all"] == 3
    assert payload["meta"]["scope_item_counts"]["top"] == 2
    assert {
        row["highlight_index"]
        for approach in approaches
        for row in payload["by_approach"][approach]["top_by_metric"]["in_degree"]
        if row["id"] == "bips:1"
    } == {0}
