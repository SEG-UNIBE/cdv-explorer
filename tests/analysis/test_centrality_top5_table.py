from analysis.dependencies.constants import (
    BODY_EXTRACTED_LLM,
    BODY_EXTRACTED_REGEX,
    PREAMBLE_EXTRACTED,
)
from paper.RQ3.dependency_centrality_table import (
    METRICS,
    export_centrality_top5_latex_table,
)


def _entries(prefix: str) -> list[dict[str, object]]:
    return [
        {
            "id": f"bips:{prefix}{rank}",
            "title": f"{prefix} title {rank}",
            "value": float(rank),
            "highlight_index": None,
        }
        for rank in range(1, 6)
    ]


def test_centrality_top5_table_omits_nonconverged_preamble_wev(tmp_path):
    approaches = [
        PREAMBLE_EXTRACTED,
        BODY_EXTRACTED_REGEX,
        BODY_EXTRACTED_LLM,
    ]
    payload = {
        "by_approach": {
            approach: {
                "top_by_metric": {
                    metric: _entries(
                        "invalid-wev"
                        if approach == PREAMBLE_EXTRACTED
                        and metric == "weighted_eigenvector"
                        else f"{approach}-{metric}"
                    )
                    for metric, _ in METRICS
                }
            }
            for approach in approaches
        }
    }
    output_path = tmp_path / "centrality_top5.tex"

    export_centrality_top5_latex_table(payload, output_path)

    latex = output_path.read_text(encoding="utf-8")
    assert "invalid-wev" not in latex
    assert latex.count(r"\multicolumn{3}{c|}{\textemdash}") == 5
    assert "did not converge" not in latex
