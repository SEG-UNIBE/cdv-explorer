from collections import Counter, defaultdict
from pathlib import Path

from paper.RQ1.classification_type import TYPE_ORDER

LATEX_TABCOLSEP_PT = 5
DIAGBOX_INNERWIDTH_CM = 2
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
        status for counts in pivot.values() for status in counts.keys()
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
    type_totals = {
        proposal_type: sum(pivot[proposal_type].values())
        for proposal_type in ordered_types
    }

    header_line = (
        " & ".join(
            [
                rf"\diagbox[innerwidth={DIAGBOX_INNERWIDTH_CM}cm]{{\textbf{{Status}}}}{{\textbf{{Type}}}}"
            ]
            + [
                rf"\begin{{tabular}}[c]{{@{{}}c@{{}}}}{_latex_escape(proposal_type)}\\({type_totals[proposal_type]})\end{{tabular}}"
                for proposal_type in ordered_types
            ]
        )
        + r" \\"
    )

    ranked_cells = sorted(
        (
            (int(pivot[proposal_type].get(status, 0)), status, proposal_type)
            for status in ordered_statuses
            for proposal_type in ordered_types
        ),
        reverse=True,
    )
    largest_cell = (ranked_cells[0][1], ranked_cells[0][2]) if ranked_cells else None

    body_lines = []
    for status in ordered_statuses:
        row_cells = [f"{_latex_escape(status)} ({status_totals[status]})"]
        for proposal_type in ordered_types:
            cell_value = _format_count_share(
                int(pivot[proposal_type].get(status, 0)),
                type_totals[proposal_type],
            )
            if (status, proposal_type) == largest_cell:
                cell_value = rf"\textbf{{{cell_value}}}"
            row_cells.append(cell_value)
        body_lines.append("        " + " & ".join(row_cells) + r" \\")

    alignment = "l|" + ("c" * len(ordered_types))
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
