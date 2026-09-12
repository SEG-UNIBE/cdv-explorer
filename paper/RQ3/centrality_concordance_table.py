from pathlib import Path
from typing import Any

METRIC_HEADERS = {
    "in_degree": "In-Degree",
    "weighted_eigenvector": "WEV",
    "pagerank": "PageRank",
    "betweenness": "BC",
}


def _latex_escape(value: object) -> str:
    return (
        str(value)
        .replace("\\", r"\textbackslash{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("$", r"\$")
        .replace("#", r"\#")
        .replace("_", r"\_")
        .replace("{", r"\{")
        .replace("}", r"\}")
    )


def export_centrality_concordance_latex_table(
    centrality_comparison: dict[str, Any], output_path: Path
) -> None:
    """Render all-IP pairwise and collective concordance across approaches."""
    meta = centrality_comparison.get("meta") or {}
    metric_order = meta.get("metric_order") or []
    approach_pairs = meta.get("approach_pairs") or []
    rows = (
        centrality_comparison.get("concordance", {})
        .get("all", {})
        .get("across_approaches", [])
    )
    rows_by_metric = {
        str(row.get("metric") or ""): row for row in rows if isinstance(row, dict)
    }
    pair_keys = [str(pair.get("key") or "") for pair in approach_pairs]
    if (
        not metric_order
        or not pair_keys
        or any(metric not in rows_by_metric for metric in metric_order)
        or any(
            pair_key not in (rows_by_metric[metric].get("pairwise_kendalls_tau_b") or {})
            for metric in metric_order
            for pair_key in pair_keys
        )
    ):
        raise ValueError(
            "Centrality comparison payload contains no complete all-IP "
            "across-approach concordance"
        )

    metric_headers = [
        _latex_escape(
            METRIC_HEADERS.get(metric)
            or rows_by_metric[metric].get("label")
            or metric
        )
        for metric in metric_order
    ]
    header_line = " & ".join(
        [r"\textbf{Comparison}"]
        + [rf"\textbf{{{header}}}" for header in metric_headers]
    )
    pairwise_maximum = max(
        float(rows_by_metric[metric]["pairwise_kendalls_tau_b"][pair["key"]])
        for pair in approach_pairs
        for metric in metric_order
    )
    body_lines = []
    for pair in approach_pairs:
        pair_label = _latex_escape(
            f"{pair['left_label']} vs. {pair['right_label']}"
        )
        values = [
            float(rows_by_metric[metric]["pairwise_kendalls_tau_b"][pair["key"]])
            for metric in metric_order
        ]
        body_lines.append(
            "        "
            + " & ".join(
                [rf"{pair_label} ($\tau_b$)"]
                + [
                    rf"\textbf{{{value:.3f}}}"
                    if value == pairwise_maximum
                    else f"{value:.3f}"
                    for value in values
                ]
            )
            + r" \\"
        )
    collective_values = [
        float(rows_by_metric[metric]["kendalls_w"]) for metric in metric_order
    ]
    collective_maximum = max(collective_values)
    collective_line = (
        "        "
        + " & ".join(
            [r"All approaches ($W$)"]
            + [
                rf"\textbf{{{value:.3f}}}"
                if value == collective_maximum
                else f"{value:.3f}"
                for value in collective_values
            ]
        )
        + r" \\"
    )

    latex = "\n".join(
        [
            r"{%",
            r"    \setlength{\abovetopsep}{0pt}%",
            r"    \setlength{\belowbottomsep}{0pt}%",
            r"    \setlength{\aboverulesep}{0pt}%",
            r"    \setlength{\belowrulesep}{0pt}%",
            r"    \setlength{\tabcolsep}{7pt}%",
            r"    \renewcommand{\arraystretch}{1.15}%",
            rf"    \begin{{tabular}}{{l|{'c' * len(metric_order)}}}",
            r"        \toprule",
            f"        {header_line}" + r" \\",
            r"        \midrule%",
            *body_lines,
            r"        \specialrule{0.65pt}{0pt}{0pt}%",
            collective_line,
            r"        \bottomrule",
            r"    \end{tabular}%",
            r"}",
            "",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(latex, encoding="utf-8")
