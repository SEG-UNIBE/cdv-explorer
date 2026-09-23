from analysis.dependencies.consistency import build_dependency_consistency_payload
from analysis.dependencies.constants import BODY_EXTRACTED_LLM, PREAMBLE_EXTRACTED


def _edge(method: str, source: str, target: str, relation_type: str) -> dict[str, object]:
    return {
        "extraction_method": method,
        "source": source,
        "target": target,
        "relation_type": relation_type,
    }


def test_consistency_payload_uses_typed_projections_and_normalizes_supersession():
    network_data = {
        "llm_model": "model-a",
        "nodes": [
            {"id": str(proposal_id), "graph_key": f"bips:{proposal_id}"}
            for proposal_id in range(1, 7)
        ],
        "dependency_edges": [
            _edge(PREAMBLE_EXTRACTED, "bips:1", "bips:2", "requires"),
            _edge(PREAMBLE_EXTRACTED, "bips:2", "bips:1", "requires"),
            _edge(PREAMBLE_EXTRACTED, "bips:3", "bips:4", "replaces"),
            _edge(
                PREAMBLE_EXTRACTED,
                "bips:4",
                "bips:3",
                "proposed_replacement",
            ),
            _edge(BODY_EXTRACTED_LLM, "bips:5", "bips:6", "depends_on"),
            _edge(BODY_EXTRACTED_LLM, "bips:6", "bips:5", "references"),
            _edge(BODY_EXTRACTED_LLM, "bips:6", "bips:5", "superseded_by"),
        ],
    }

    payload = build_dependency_consistency_payload(network_data)
    preamble = payload["by_approach"][PREAMBLE_EXTRACTED]
    llm = payload["by_approach"][BODY_EXTRACTED_LLM]

    assert payload["meta"]["llm_model"] == "model-a"
    assert preamble["dependency"]["edge_count"] == 2
    assert preamble["dependency"]["cyclic_group_count"] == 1
    assert preamble["dependency"]["involved_node_count"] == 2
    assert preamble["dependency"]["self_relation_count"] == 0
    assert preamble["supersession"]["fact_count"] == 1
    assert preamble["supersession"]["reciprocal_count"] == 1
    assert llm["dependency"]["edge_count"] == 1
    assert llm["dependency"]["cyclic_group_count"] == 0
    assert llm["supersession"]["one_sided_count"] == 1


def test_consistency_payload_surfaces_nonzero_structural_checks():
    network_data = {
        "nodes": [{"id": "1", "graph_key": "bips:1"}],
        "dependency_edges": [
            _edge(PREAMBLE_EXTRACTED, "bips:1", "bips:1", "requires"),
            _edge(PREAMBLE_EXTRACTED, "bips:1", "bips:999", "requires"),
        ],
    }

    payload = build_dependency_consistency_payload(network_data)
    preamble = payload["by_approach"][PREAMBLE_EXTRACTED]

    assert preamble["checks"]["self_relation_count"] == 1
    assert preamble["checks"]["unresolved_target_count"] == 1
    assert preamble["dependency"]["self_relation_count"] == 1
    assert preamble["dependency"]["unresolved_target_count"] == 1
    assert preamble["supersession"]["self_relation_count"] == 0
    assert "Self-relations" not in payload["omitted_zero_checks"]
    assert any(row["metric"] == "Self-relations" for row in payload["table_rows"])
    assert any(
        row["group"] == "Dependency"
        and row["metric"] == "Self-relations"
        and row["values"][PREAMBLE_EXTRACTED] == "1"
        for row in payload["dashboard_table_rows"]
    )
