from analysis.dependencies.constants import GROUND_TRUTH_CURATED
from paper.RQ2.ground_truth_dataset_table import (
    export_ground_truth_dataset_latex_table,
)


def _edge(source: str, target: str, relation_type: str) -> dict[str, object]:
    return {
        "source": source,
        "target": target,
        "relation_type": relation_type,
        "extraction_method": GROUND_TRUTH_CURATED,
    }


def test_dataset_composition_uses_separate_node_and_edge_denominators(tmp_path):
    network_data = {
        "ground_truth_reviewed_ips": [
            {
                "ip": "bips:1",
                "status": "Draft",
                "type": "Specification",
            },
            {
                "ip": "bips:2",
                "status": "Closed",
                "type": "Informational",
            },
        ],
        "dependency_edges": [
            _edge("bips:1", "bips:2", "depends_on"),
            _edge("bips:2", "bips:1", "references"),
            _edge("bips:1", "slips:1", "references"),
        ],
    }
    output_path = tmp_path / "composition.tex"

    export_ground_truth_dataset_latex_table(network_data, output_path)

    latex = output_path.read_text(encoding="utf-8")
    assert latex.count("Reviewed & 2 & 100.0\\%") == 2
    assert r"\texttt{depends\_on} & 1 & 50.0\%" in latex
    assert r"\texttt{references} & 1 & 50.0\%" in latex
