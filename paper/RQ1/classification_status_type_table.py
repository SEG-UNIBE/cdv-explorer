from collections import Counter, defaultdict
from pathlib import Path

from paper.RQ1.classification_type import TYPE_ORDER


LATEX_TABCOLSEP_PT = 5
DIAGBOX_INNERWIDTH_CM = 2.8
TABLE_STATUS_ORDER = [
    "Draft",
    "Complete",
    "Deployed",
    "Closed",
]


def _latex_escape(value: str) -> str:
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
        .replace("~", r"\textasciitilde{}")
        .replace("^", r"\textasciicircum{}")
    )


def _ordered_categories(observed: set[str], preferred_order: list[str]) -> list[str]:
    ordered = [value for value in preferred_order if value in observed]
    ordered.extend(sorted(observed - set(ordered)))
    return ordered


def _format_count_share(count: int, total: int) -> str:
    share = (count / total * 100) if total > 0 else 0.0
    return f"{count} ({share:.1f}\\%)"


def export_classification_status_type_latex_table(
    network_data: dict,
    output_path: Path,
    snapshot_label: str,
    *,
    tabcolsep_pt: int = LATEX_TABCOLSEP_PT,
) -> None:
    nodes = network_data.get("nodes", [])
    pivot = defaultdict(Counter)

    for node in nodes:
        status = str(node.get("status")).strip() or "Unknown Status"
        proposal_type = str(node.get("type")).strip() or "Unknown Type"
        pivot[proposal_type][status] += 1

    observed_types = set(pivot.keys())
    observed_statuses = {
        status
        for counts in pivot.values()
        for status in counts.keys()
    }
    ordered_types = _ordered_categories(observed_types, TYPE_ORDER)
    ordered_statuses = _ordered_categories(
        observed_statuses,
        TABLE_STATUS_ORDER,
    )
    status_totals = {
        status: sum(pivot[t].get(status, 0) for t in ordered_types)
        for status in ordered_statuses
    }

    header_line = " & ".join(
        [
            rf"\diagbox[innerwidth={DIAGBOX_INNERWIDTH_CM}cm]{{\textbf{{Type}}}}{{\textbf{{Status}}}}"
        ]
        + [f"{_latex_escape(status)} ({status_totals[status]})" for status in ordered_statuses]
    ) + r" \\"

    body_lines = []
    for proposal_type in ordered_types:
        row_total = sum(pivot[proposal_type].values())
        row_cells = [f"{_latex_escape(proposal_type)} ({row_total})"]
        for status in ordered_statuses:
            cell_value = _format_count_share(
                int(pivot[proposal_type].get(status, 0)),
                row_total,
            )
            row_cells.append(cell_value)
        body_lines.append("        " + " & ".join(row_cells) + r" \\")

    alignment = "l|" + ("c" * len(ordered_statuses))
    latex_table = "\n".join(
        [
            "{%",
            r"    \setlength{\abovetopsep}{0pt}%",
            r"    \setlength{\belowbottomsep}{0pt}%",
            r"    \setlength{\aboverulesep}{0pt}%",
            r"    \setlength{\belowrulesep}{0pt}%",
            rf"    \setlength{{\tabcolsep}}{{{tabcolsep_pt}pt}}%",
            r"    \renewcommand{\arraystretch}{1.15}%",
            rf"    \begin{{tabular}}{{{alignment}}}",
            r"        \toprule",
            f"        {header_line}",
            r"        \midrule%",
            *body_lines,
            r"        \bottomrule",
            r"    \end{tabular}%",
            "}",
            "",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(latex_table, encoding="utf-8")
