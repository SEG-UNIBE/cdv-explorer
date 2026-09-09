from pathlib import Path
from typing import Any


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


def export_dependency_consistency_latex_table(
    payload: dict[str, Any], output_path: Path
) -> None:
    """Render the precomputed consistency summary without recomputing metrics."""
    approach_order = payload.get("meta", {}).get("approach_order", [])
    by_approach = payload.get("by_approach", {})
    table_rows = payload.get("table_rows", [])
    if not approach_order or not table_rows:
        raise ValueError("Dependency consistency payload contains no table data")

    headers = [
        _latex_escape(by_approach.get(key, {}).get("label") or key)
        for key in approach_order
    ]
    body_lines: list[str] = []
    previous_group: str | None = None
    for row in table_rows:
        group = str(row.get("group") or "")
        if previous_group is not None and group != previous_group:
            body_lines.append(r"        \midrule%")
        group_cell = rf"\textbf{{{_latex_escape(group)}}}" if group != previous_group else ""
        values = row.get("values", {})
        cells = [
            group_cell,
            _latex_escape(row.get("metric") or ""),
            *[_latex_escape(values.get(key, "--")) for key in approach_order],
        ]
        body_lines.append("        " + " & ".join(cells) + r" \\")
        previous_group = group

    latex = "\n".join(
        [
            r"{%",
            r"    \setlength{\abovetopsep}{0pt}%",
            r"    \setlength{\belowbottomsep}{0pt}%",
            r"    \setlength{\aboverulesep}{0pt}%",
            r"    \setlength{\belowrulesep}{0pt}%",
            r"    \setlength{\tabcolsep}{7pt}%",
            r"    \renewcommand{\arraystretch}{1.15}%",
            rf"    \begin{{tabular}}{{ll|{'c' * len(approach_order)}}}",
            r"        \toprule",
            "        "
            + " & ".join(
                [r"\textbf{Relation}", r"\textbf{Measure}"]
                + [rf"\textbf{{{header}}}" for header in headers]
            )
            + r" \\",
            r"        \midrule%",
            *body_lines,
            r"        \bottomrule",
            r"    \end{tabular}%",
            r"}",
            "",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(latex, encoding="utf-8")
