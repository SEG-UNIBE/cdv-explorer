from analysis.dependencies.constants import (
    BODY_EXTRACTED_LLM,
    BODY_EXTRACTED_REGEX,
    PREAMBLE_EXTRACTED,
)
from paper.RQ2.dependency_differential_plots import (
    _build_comparison_edges,
    _build_layout_graph,
    _extract_exported_node_ids,
    _normalize_edge_keys,
)


def _edge(source, target, extraction_method):
    return {
        "source": f"bips:{source}",
        "target": f"bips:{target}",
        "extraction_method": extraction_method,
        "relation_type": "reference",
    }


def test_layout_export_node_ids_define_the_visible_set():
    payload = {
        "nodes": [
            {"id": "20", "graph_id": "bips:20"},
            {"id": "21", "graph_id": "bips:21"},
        ],
        "positions": {"bips:20": [1, 2], "bips:21": [3, 4]},
    }

    assert _extract_exported_node_ids(payload) == {"20", "21"}


def test_visible_nodes_form_an_induced_dependency_graph():
    network_data = {
        "nodes": [
            {"id": "1", "type": "Specification"},
            {"id": "2", "type": "Specification"},
            {"id": "3", "type": "Process"},
            {"id": "4", "type": "Process"},
        ],
        "dependency_edges": [
            _edge(1, 2, PREAMBLE_EXTRACTED),
            _edge(2, 3, BODY_EXTRACTED_REGEX),
            _edge(3, 4, BODY_EXTRACTED_LLM),
        ],
    }

    graph = _build_layout_graph(network_data, {"1", "2", "3"}, {"1"})

    assert set(graph.edges()) == {("1", "2"), ("2", "3")}


def test_explicit_edge_set_defines_nodes_and_edges():
    network_data = {
        "nodes": [
            {"id": "1", "type": "Specification"},
            {"id": "2", "type": "Specification"},
            {"id": "3", "type": "Process"},
        ],
        "dependency_edges": [
            _edge(1, 2, PREAMBLE_EXTRACTED),
            _edge(2, 3, BODY_EXTRACTED_REGEX),
        ],
    }
    included_edges = _normalize_edge_keys([(1, 2)])

    graph = _build_layout_graph(
        network_data,
        {"1", "2"},
        set(),
        include_edges=included_edges,
    )

    assert set(graph.nodes()) == {"1", "2"}
    assert set(graph.edges()) == {("1", "2")}


def test_comparison_includes_edges_between_non_focus_visible_nodes():
    edges = [
        _edge(1, 2, PREAMBLE_EXTRACTED),
        _edge(2, 3, PREAMBLE_EXTRACTED),
        _edge(2, 3, BODY_EXTRACTED_REGEX),
        _edge(3, 4, BODY_EXTRACTED_REGEX),
    ]

    comparison = _build_comparison_edges(
        edges,
        approach_type=BODY_EXTRACTED_REGEX,
        baseline_type=PREAMBLE_EXTRACTED,
        display_ids={"1", "2", "3"},
        include_edges={("1", "2"), ("2", "3")},
    )

    assert comparison == {
        "approach_only": [],
        "overlap": [("2", "3")],
        "baseline_only": [("1", "2")],
    }
