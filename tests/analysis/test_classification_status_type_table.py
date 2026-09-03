from pathlib import Path

from paper.RQ1.classification_status_type_table import (
    export_classification_status_type_latex_table,
)


def test_bolds_modal_status_within_each_type_column(tmp_path: Path) -> None:
    network_data = {
        "nodes": [
            {"status": "Draft", "type": "Specification"},
            {"status": "Draft", "type": "Specification"},
            {"status": "Complete", "type": "Specification"},
            {"status": "Draft", "type": "Informational"},
            {"status": "Complete", "type": "Informational"},
            {"status": "Complete", "type": "Informational"},
            {"status": "Complete", "type": "Informational"},
        ]
    }
    output_path = tmp_path / "classification_status_type.tex"

    export_classification_status_type_latex_table(
        network_data,
        output_path,
        snapshot_label="Test snapshot",
    )

    latex = output_path.read_text(encoding="utf-8")
    assert r"\textbf{2 (66.7\%)}" in latex
    assert r"\textbf{3 (75.0\%)}" in latex
    assert r"\textbf{1 (33.3\%)}" not in latex
    assert r"\textbf{1 (25.0\%)}" not in latex
