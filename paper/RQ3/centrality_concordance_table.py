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
    """Render all-IP concordance across extraction approaches."""
    meta = centrality_comparison.get("meta") or {}
    metric_order = meta.get("metric_order") or []
    rows = (
        centrality_comparison.get("concordance", {})
        .get("all", {})
        .get("across_approaches", [])
    )
    rows_by_metric = {
        str(row.get("metric") or ""): row for row in rows if isinstance(row, dict)
    }
    if not metric_order or any(metric not in rows_by_metric for metric in metric_order):
        raise ValueError(
            "Centrality comparison payload contains no complete all-IP "
            "across-approach concordance"
        )

    ordered_rows = [rows_by_metric[metric] for metric in metric_order]
    values = [float(row["kendalls_w"]) for row in ordered_rows]
    maximum = max(values)
    formatted_values = []
    for value in values:
        formatted_value = f"{value:.3f}"
        if value == maximum:
            formatted_value = rf"\textbf{{{formatted_value}}}"
        formatted_values.append(formatted_value)

    metric_headers = [
        _latex_escape(
            METRIC_HEADERS.get(metric)
            or rows_by_metric[metric].get("label")
            or metric
        )
        for metric in metric_order
    ]
    header_line = " & ".join(
        [""] + [rf"\textbf{{{header}}}" for header in metric_headers]
    )
    value_line = " & ".join(
        [r"\textbf{Kendall's $W$}"] + formatted_values
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
            f"        {value_line}" + r" \\",
            r"        \bottomrule",
            r"    \end{tabular}%",
            r"}",
            "",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(latex, encoding="utf-8")
