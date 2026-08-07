from pathlib import Path

from analysis.dependencies.constants import (
    BODY_EXTRACTED_REGEX,
    DEPENDENCY_APPROACH_SHORT_LABELS,
)
from paper.RQ2.ground_truth_evaluation import (
    DOE_TYPE_MAPPING,
    ETA_TYPE_MAPPING,
    EVALUATED_APPROACHES,
    EXTRACTION_SUBTYPE_ALL,
    GT_TYPE_ALL,
)

LATEX_TABCOLSEP_PT = 8
LATEX_ARRAYSTRETCH = 1.2
SHORT_LABELS = DEPENDENCY_APPROACH_SHORT_LABELS
GT_TYPE_ALL_LABEL = r"\textit{(any)}"
UNTYPED_LABEL = "-"
# Thicker than \midrule but lighter than \toprule/\bottomrule, to set the two
# Mode groups apart without looking like an outer table edge.
MEDIUM_RULE = r"\specialrule{0.65pt}{0pt}{0pt}"
APPROACH_GROUP_RULE = r"\cmidrule(lr){2-7}"

# Each mode's mapping is the same one actually used to compute the
# ground-truth evaluation plots (see ETA_TYPE_MAPPING / DOE_TYPE_MAPPING in
# ground_truth_evaluation.py), so this table always documents the real scoring
# rules rather than a copy that can drift from them.
MAPPING_GROUPS: list[dict] = [
    {
        "label": "Edge type agnostic (ETA)",
        "mapping": ETA_TYPE_MAPPING,
    },
    {
        "label": "Dependency-only edges (DOE)",
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


def _approach_label(approach: str) -> str:
    return SHORT_LABELS.get(approach, approach)


def _edge_type_cell(approach: str, subtype: str) -> str:
    if subtype == EXTRACTION_SUBTYPE_ALL:
        if approach == BODY_EXTRACTED_REGEX:
            return UNTYPED_LABEL
        return GT_TYPE_ALL_LABEL
    if approach == BODY_EXTRACTED_REGEX:
        return UNTYPED_LABEL
    return _code(subtype)


def _normalize_relation_type(relation_type: object) -> str:
    return str(relation_type or "").strip().lower()


def _edges_by_method(network_data: dict | None, extraction_method: str) -> list[dict]:
    if not network_data:
        return []
    return [
        edge
        for edge in network_data.get("dependency_edges", [])
        if edge.get("extraction_method") == extraction_method
    ]


def _reviewed_scope_edges(
    network_data: dict | None, extraction_method: str
) -> list[dict]:
    edges = _edges_by_method(network_data, extraction_method)
    if not network_data:
        return edges
    reviewed_source_keys = {
        str(entry.get("ip") or "").strip()
        for entry in network_data.get("ground_truth_reviewed_ips", [])
        if str(entry.get("ip") or "").strip()
    }
    if not reviewed_source_keys:
        return edges
    reviewed_catalogs = {
        key.partition(":")[0] for key in reviewed_source_keys if ":" in key
    }
    return [
        edge
        for edge in edges
        if str(edge.get("source") or "").strip() in reviewed_source_keys
        and str(edge.get("target") or "").strip().partition(":")[0] in reviewed_catalogs
    ]


def _subtype_count(
    network_data: dict | None,
    approach: str,
    subtype: str,
) -> int | None:
    if network_data is None:
        return None
    edges = _reviewed_scope_edges(network_data, approach)
    if subtype == EXTRACTION_SUBTYPE_ALL:
        return len(edges)
    return sum(
        1
        for edge in edges
        if _normalize_relation_type(edge.get("relation_type")) == subtype
    )


def _build_group_rows(
    mapping: dict[str, dict[str, str]],
    group_label: str,
    *,
    network_data: dict | None = None,
) -> list[str]:
    rows = [
        (approach, subtype, target)
        for approach in EVALUATED_APPROACHES
        for subtype, target in mapping.get(approach, {}).items()
    ]
    approach_row_counts = {
        approach: len(mapping.get(approach, {})) for approach in EVALUATED_APPROACHES
    }
    approach_totals = {
        approach: sum(
            count or 0
            for subtype in mapping.get(approach, {})
            for count in [_subtype_count(network_data, approach, subtype)]
        )
        for approach in EVALUATED_APPROACHES
        if network_data is not None and mapping.get(approach)
    }
    seen_approaches: set[str] = set()

    body_lines = []
    for row_index, (approach, subtype, target) in enumerate(rows):
        previous_approach = rows[row_index - 1][0] if row_index else None
        if previous_approach is not None and previous_approach != approach:
            body_lines.append(f"        {APPROACH_GROUP_RULE}")
        subtype_count = _subtype_count(network_data, approach, subtype)
        cells = []
        if row_index == 0:
            cells.append(
                rf"\multirow{{{len(rows)}}}{{*}}{{{_latex_escape(group_label)}}}"
            )
        else:
            cells.append("")
        if approach not in seen_approaches:
            row_count = approach_row_counts.get(approach, 1)
            approach_count = approach_totals.get(approach)
            cells.append(
                rf"\multirow{{{row_count}}}{{*}}{{{_approach_label(approach)}}}"
            )
            cells.append(
                rf"\multirow{{{row_count}}}{{*}}{{{approach_count if approach_count is not None else ''}}}"
            )
            seen_approaches.add(approach)
        else:
            cells.append("")
            cells.append("")
        cells.append(_edge_type_cell(approach, subtype))
        cells.append("" if subtype_count is None else str(subtype_count))
        cells.append(r"$\rightarrow$")
        cells.append(GT_TYPE_ALL_LABEL if target == GT_TYPE_ALL else _code(target))
        body_lines.append("        " + " & ".join(cells) + r" \\")
    return body_lines


def export_type_mapping_latex_table(
    output_path: Path,
    *,
    network_data: dict | None = None,
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
        body_lines.extend(
            _build_group_rows(
                group["mapping"],
                group["label"],
                network_data=network_data,
            )
        )
        if group_index < len(groups) - 1:
            body_lines.append(f"        {MEDIUM_RULE}%")

    header_line = (
        " & ".join(
            [
                r"\textbf{Mode}",
                r"\textbf{Approach}",
                r"\textbf{Total}",
                r"\textbf{Edge Type}",
                r"\textbf{Count}",
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
            r"    \begin{tabular}{c|l r l r c l}",
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
