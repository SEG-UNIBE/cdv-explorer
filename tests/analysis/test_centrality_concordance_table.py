from paper.RQ3.centrality_concordance_table import (
    export_centrality_concordance_latex_table,
)


def test_centrality_concordance_table_uses_all_ip_scope(tmp_path):
    payload = {
        "meta": {
            "metric_order": ["in_degree", "pagerank"],
        },
        "concordance": {
            "top": {
                "across_approaches": [
                    {"metric": "in_degree", "label": "In-Degree", "kendalls_w": 0.1},
                    {"metric": "pagerank", "label": "PageRank", "kendalls_w": 0.2},
                ]
            },
            "all": {
                "across_approaches": [
                    {"metric": "in_degree", "label": "In-Degree", "kendalls_w": 0.75},
                    {"metric": "pagerank", "label": "PageRank", "kendalls_w": 0.7},
                ]
            },
        },
    }
    output_path = tmp_path / "centrality_concordance.tex"

    export_centrality_concordance_latex_table(payload, output_path)

    latex = output_path.read_text(encoding="utf-8")
    assert r"\textbf{In-Degree} & \textbf{PageRank}" in latex
    assert r"\textbf{Kendall's $W$} & \textbf{0.750} & 0.700" in latex
    assert "0.100" not in latex
