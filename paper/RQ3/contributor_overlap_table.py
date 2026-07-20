from pathlib import Path
from typing import Any, Mapping

from analysis.authorship.metrics import (
    build_contributor_coverage,
    build_contributor_overlap_breakdown,
)

LATEX_TABCOLSEP_PT = 6
LATEX_ARRAYSTRETCH = 1.15
# Thicker than \midrule but lighter than \toprule/\bottomrule, to set the two
# blocks apart without looking like an outer table edge.
MEDIUM_RULE = r"\specialrule{0.65pt}{0pt}{0pt}"
# A_o = originators, A_c = contributors (per proposal, for the second block).
ORIGINATORS = r"A_o"
CONTRIBUTORS = r"A_c"


def _count_row(label: str, formula: str, count: int) -> tuple[str, str, str]:
    return label, formula, str(count)


def _share_row(
    label: str, formula: str, count: int, total: int
) -> tuple[str, str, str]:
    share = f"{count / total * 100:.1f}\\%" if total else ""
    value = f"{count} ({share})" if share else str(count)
    return label, formula, value


def _basis_block(basis: str, rows: list[tuple[str, str, str]]) -> list[str]:
    lines = []
    for row_index, cells in enumerate(rows):
        basis_cell = rf"\multirow{{{len(rows)}}}{{*}}{{{basis}}}" if row_index == 0 else ""
        lines.append("        " + " & ".join([basis_cell, *cells]) + r" \\")
    return lines


def export_contributor_overlap_latex_table(
    network_data: dict[str, Any],
    authorship_payload: dict[str, Any],
    output_path: Path,
    *,
    tabcolsep_pt: int = LATEX_TABCOLSEP_PT,
) -> None:
    """Declare formal-originator vs. git-contributor set sizes and their
    per-proposal overlap (see analysis/authorship/metrics.py's
    build_contributor_coverage / build_contributor_overlap_breakdown, the
    source of truth this table renders)."""
    nodes = network_data.get("nodes", [])
    aliases: Mapping[str, str] = authorship_payload.get("meta", {}).get(
        "author_aliases", {}
    )
    coverage = build_contributor_coverage(nodes, aliases)
    overlap = build_contributor_overlap_breakdown(nodes, aliases)

    declared_only = coverage["declared_author_count"] - coverage["contributors_also_declared"]
    proposal_count = overlap["proposal_count"]

    person_rows = [
        _count_row(
            "Declared Originators", rf"$|{ORIGINATORS}|$", coverage["declared_author_count"]
        ),
        _count_row(
            "Git Contributors", rf"$|{CONTRIBUTORS}|$", coverage["contributor_count"]
        ),
        _count_row(
            "In Both Roles",
            rf"$|{ORIGINATORS} \cap {CONTRIBUTORS}|$",
            coverage["contributors_also_declared"],
        ),
        _count_row(
            "Originators Only",
            rf"$|{ORIGINATORS} \setminus {CONTRIBUTORS}|$",
            declared_only,
        ),
        _count_row(
            "Contributors Only",
            rf"$|{CONTRIBUTORS} \setminus {ORIGINATORS}|$",
            coverage["contributors_never_declared"],
        ),
    ]
    ip_rows = [
        _share_row(
            "Only Edited by Originators",
            rf"${CONTRIBUTORS} \subseteq {ORIGINATORS}$",
            overlap["contributors_within_originators"],
            proposal_count,
        ),
        _share_row(
            "Edited by at Least 1 Originator",
            rf"${ORIGINATORS} \cap {CONTRIBUTORS} \neq \emptyset$",
            overlap["originator_contributor_overlap"],
            proposal_count,
        ),
        _share_row(
            "Only Edited by Non-Originators",
            rf"${ORIGINATORS} \cap {CONTRIBUTORS} = \emptyset$",
            overlap["no_originator_contributor_overlap"],
            proposal_count,
        ),
    ]

    body_lines = [
        *_basis_block("Person", person_rows),
        f"        {MEDIUM_RULE}%",
        *_basis_block("IP", ip_rows),
    ]

    header_line = (
        " & ".join(
            [
                r"\textbf{Basis}",
                r"\textbf{Metric}",
                r"\textbf{Formula}",
                r"\textbf{Count}",
            ]
        )
        + r" \\"
    )

    latex_table = "\n".join(
        [
            "{%",
            r"    \setlength{\abovetopsep}{0pt}%",
            r"    \setlength{\belowbottomsep}{0pt}%",
            r"    \setlength{\aboverulesep}{0pt}%",
            r"    \setlength{\belowrulesep}{0pt}%",
            rf"    \setlength{{\tabcolsep}}{{{tabcolsep_pt}pt}}%",
            rf"    \renewcommand{{\arraystretch}}{{{LATEX_ARRAYSTRETCH}}}%",
            r"    \begin{tabular}{c|lcc}",
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
