from analysis.dependencies.constants import BODY_EXTRACTED_LLM, PREAMBLE_EXTRACTED
from paper.RQ2.dependency_consistency_table import (
    export_dependency_consistency_latex_table,
)


def test_consistency_table_renders_precomputed_rows(tmp_path):
    payload = {
        "meta": {"approach_order": [PREAMBLE_EXTRACTED, BODY_EXTRACTED_LLM]},
        "by_approach": {
            PREAMBLE_EXTRACTED: {"label": "Preamble"},
            BODY_EXTRACTED_LLM: {"label": "LLM"},
        },
        "table_rows": [
            {
                "group": "Dependency",
                "metric": "Cyclic groups (SCCs)",
                "values": {PREAMBLE_EXTRACTED: "1", BODY_EXTRACTED_LLM: "7"},
            }
        ],
    }
    output_path = tmp_path / "consistency.tex"

    export_dependency_consistency_latex_table(payload, output_path)

    latex = output_path.read_text(encoding="utf-8")
    assert "Cyclic groups (SCCs) & 1 & 7" in latex
