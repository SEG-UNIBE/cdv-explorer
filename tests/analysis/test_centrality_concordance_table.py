from paper.RQ3.centrality_concordance_table import (
    export_centrality_concordance_latex_table,
)


def test_centrality_concordance_table_uses_all_ip_scope(tmp_path):
    pair_key = "preamble_extracted__body_extracted_llm"
    payload = {
        "meta": {
            "metric_order": ["in_degree", "pagerank"],
            "approach_pairs": [
                {
                    "key": pair_key,
                    "left_label": "Preamble",
                    "right_label": "LLM",
                }
            ],
        },
        "concordance": {
            "top": {
                "across_approaches": [
                    {
                        "metric": "in_degree",
                        "label": "In-Degree",
                        "kendalls_w": 0.1,
                        "pairwise_kendalls_tau_b": {pair_key: 0.2},
                    },
                    {
                        "metric": "pagerank",
                        "label": "PageRank",
                        "kendalls_w": 0.2,
                        "pairwise_kendalls_tau_b": {pair_key: 0.3},
                    },
                ]
            },
            "all": {
                "across_approaches": [
                    {
                        "metric": "in_degree",
                        "label": "In-Degree",
                        "kendalls_w": 0.75,
                        "pairwise_kendalls_tau_b": {pair_key: 0.6},
                    },
                    {
                        "metric": "pagerank",
                        "label": "PageRank",
                        "kendalls_w": 0.7,
                        "pairwise_kendalls_tau_b": {pair_key: 0.8},
                    },
                ]
            },
        },
    }
    output_path = tmp_path / "centrality_concordance.tex"

    export_centrality_concordance_latex_table(payload, output_path)

    latex = output_path.read_text(encoding="utf-8")
    assert (
        r"\textbf{Comparison} & \textbf{In-Degree} & \textbf{PageRank}"
        in latex
    )
    assert (
        r"Preamble vs. LLM ($\tau_b$) & 0.600 & \textbf{0.800}"
        in latex
    )
    assert r"All approaches ($W$) & \textbf{0.750} & 0.700" in latex
    assert "0.100" not in latex
