from pathlib import Path

from analysis.dependencies.constants import (
    DEPENDENCY_APPROACH_SHORT_LABELS,
    PREAMBLE_EXTRACTED,
)
from paper.RQ2.ground_truth_evaluation import (
    DOE_TYPE_MAPPING,
    ETA_TYPE_MAPPING,
    EVALUATED_APPROACHES,
    GT_TYPE_ALL,
)

LATEX_TABCOLSEP_PT = 6
LATEX_ARRAYSTRETCH = 1.2
SHORT_LABELS = DEPENDENCY_APPROACH_SHORT_LABELS
GT_TYPE_ALL_LABEL = r"\textit{(any)}"
# Thicker than \midrule but lighter than \toprule/\bottomrule, to set the two
# Mode groups apart without looking like an outer table edge.
MEDIUM_RULE = r"\specialrule{0.65pt}{0pt}{0pt}"

# Each mode's mapping is the same one actually used to compute the
# ground-truth evaluation plots (see ETA_TYPE_MAPPING / DOE_TYPE_MAPPING in
# ground_truth_evaluation.py), so this table always documents the real scoring
# rules rather than a copy that can drift from them.
MAPPING_GROUPS: list[dict] = [
    {
        "label": ["Edge type", "agnostic", "(ETA)"],
        "mapping": ETA_TYPE_MAPPING,
    },
    {
        "label": ["Dependency-", "only edges", "(DOE)"],
        "mapping": DOE_TYPE_MAPPING,
    },
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


def _code(value: str) -> str:
    return rf"\texttt{{{_latex_escape(value)}}}"


def _stacked(lines: list[str], *, bold: bool = False) -> str:
    """Render `lines` as a centered, line-broken cell, so a long label can
    wrap without widening the column to its full length."""
    styled = [rf"\textbf{{{line}}}" if bold else line for line in lines]
    body = r"\\".join(styled)
    return rf"\begin{{tabular}}[c]{{@{{}}c@{{}}}}{body}\end{{tabular}}"


def _subtype_cell(approach: str, subtype: str) -> str:
    approach_label = SHORT_LABELS.get(approach, approach)
    # Preamble carries multiple subtypes per group, so each needs its own
    # subtype label; Regex/LLM always contribute exactly one subtype per
    # group, so the approach name alone is unambiguous.
    if approach == PREAMBLE_EXTRACTED:
        return f"{approach_label}:{_code(subtype)}"
    return approach_label


def _build_group_rows(
    mapping: dict[str, dict[str, str]], group_label_lines: list[str]
) -> list[str]:
    rows = [
        (approach, subtype, target)
        for approach in EVALUATED_APPROACHES
        for subtype, target in mapping.get(approach, {}).items()
    ]

    body_lines = []
    for row_index, (approach, subtype, target) in enumerate(rows):
        cells = []
        if row_index == 0:
            cells.append(
                rf"\multirow{{{len(rows)}}}{{*}}{{{_stacked(group_label_lines)}}}"
            )
        else:
            cells.append("")
        cells.append(_subtype_cell(approach, subtype))
        cells.append(r"$\rightarrow$")
        cells.append(GT_TYPE_ALL_LABEL if target == GT_TYPE_ALL else _code(target))
        body_lines.append("        " + " & ".join(cells) + r" \\")
    return body_lines


def export_type_mapping_latex_table(
    output_path: Path,
    *,
    groups: list[dict] | None = None,
    tabcolsep_pt: int = LATEX_TABCOLSEP_PT,
) -> None:
    """Declare, per Mode, the subtype -> ground-truth relation-type mapping
    each approach is scored against: Edge type agnostic (ETA) credits a
    subtype for any ground-truth relation type on the same directed edge,
    while Dependency-only edges (DOE) credits it only against depends_on."""
    groups = groups if groups is not None else MAPPING_GROUPS

    body_lines = []
    for group_index, group in enumerate(groups):
        body_lines.extend(_build_group_rows(group["mapping"], group["label"]))
        if group_index < len(groups) - 1:
            body_lines.append(f"        {MEDIUM_RULE}%")

    header_line = (
        " & ".join(
            [
                r"\textbf{Mode}",
                r"\textbf{Approach Type}",
                "",
                r"\textbf{GT Type}",
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
            r"    \begin{tabular}{c|l c l}",
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
