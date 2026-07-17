from pathlib import Path
from typing import Any

from analysis.dependencies.constants import (
    BODY_EXTRACTED_LLM,
    BODY_EXTRACTED_REGEX,
    DEPENDENCY_APPROACH_SHORT_LABELS,
    PREAMBLE_EXTRACTED,
)
from analysis.dependencies.metrics import _build_pairwise_comparisons

LATEX_TABCOLSEP_PT = 4
APPROACH_ORDER = [
    PREAMBLE_EXTRACTED,
    BODY_EXTRACTED_REGEX,
    BODY_EXTRACTED_LLM,
]
SHORT_LABELS = DEPENDENCY_APPROACH_SHORT_LABELS
PREAMBLE_ONLY_COLUMN_ORDER = [
    BODY_EXTRACTED_REGEX,
    BODY_EXTRACTED_LLM,
]
REGEX_VS_LLM_COLUMN_ORDER = [
    BODY_EXTRACTED_LLM,
]
METRIC_ORDER = [r"$A \cap B$", r"$A' \cap B$", r"$A \cap B'$"]
KAPPA_METRIC_LABEL = r"$\kappa$"
# Grey level for the self-comparison diagonal (0 = black, 1 = white).
DIAGONAL_GRAY_LEVEL = 0.65


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


def _format_count_share(count: int, share: float) -> str:
    return f"{count} ({share * 100:.1f}\\%)"


def _get_approach_only_rate(summary: dict[str, Any]) -> float:
    approach_total = int(summary.get("approach_total", 0) or 0)
    if approach_total <= 0:
        return 0.0
    return float(summary.get("approach_only", 0) or 0) / approach_total


def _format_kappa(summary: dict[str, Any]) -> str:
    kappa = summary.get("kappa")
    return "--" if kappa is None else f"{float(kappa):.2f}"


def _build_cell(comparison: dict[str, Any]) -> dict[str, str]:
    summary = comparison.get("summary", {})
    return {
        r"$A \cap B$": _format_count_share(
            int(summary.get("overlap", 0) or 0),
            float(summary.get("hit_rate", 0.0) or 0.0),
        ),
        r"$A \cap B'$": _format_count_share(
            int(summary.get("approach_only", 0) or 0),
            _get_approach_only_rate(summary),
        ),
        r"$A' \cap B$": _format_count_share(
            int(summary.get("baseline_only", 0) or 0),
            float(summary.get("missed_rate", 0.0) or 0.0),
        ),
        KAPPA_METRIC_LABEL: _format_kappa(summary),
    }


def _get_pairwise_summary(
    pairwise_comparisons: dict[str, Any],
    *,
    approach: str,
    baseline: str,
) -> dict[str, Any]:
    return (pairwise_comparisons.get(f"{approach}__vs__{baseline}") or {}).get(
        "summary", {}
    )


def _format_approach_label_with_total(label: str, total: int) -> str:
    return f"{label} ({total})"


def _format_bold_label_with_plain_total(label: str, total: int) -> str:
    return rf"\textbf{{{_latex_escape(label)}}} ({total})"


def _format_bold_label_with_plain_total_stacked(label: str, total: int) -> str:
    return (
        rf"\begin{{tabular}}[c]{{@{{}}c@{{}}}}"
        rf"\textbf{{{_latex_escape(label)}}}\\"
        rf"({total})"
        rf"\end{{tabular}}"
    )


def _format_fixed_width_stacked_label(label: str, total: int, width_macro: str) -> str:
    return (
        rf"\parbox{{{width_macro}}}{{\centering "
        rf"\textbf{{{_latex_escape(label)}}}\\({total})}}"
    )


def _build_label_width_setup(width_macro: str, labels: list[str]) -> list[str]:
    """Emit LaTeX that sets ``width_macro`` to the widest of ``labels``.

    Used so separately rendered tabulars share the exact same first-column
    width regardless of which approach label happens to be widest.
    """
    scratch_macro = f"{width_macro}Scratch"
    lines = [
        rf"    \ifdefined{width_macro}\else\newlength{{{width_macro}}}\fi%",
        rf"    \ifdefined{scratch_macro}\else\newlength{{{scratch_macro}}}\fi%",
        rf"    \setlength{{{width_macro}}}{{0pt}}%",
    ]
    for label in labels:
        lines.extend(
            [
                rf"    \settowidth{{{scratch_macro}}}{{{label}}}%",
                rf"    \ifdim{scratch_macro}>{width_macro}"
                rf"\setlength{{{width_macro}}}{{{scratch_macro}}}\fi%",
            ]
        )
    return lines


def _indent_block(block: str, prefix: str = "    ") -> list[str]:
    return [f"{prefix}{line}" if line else line for line in block.splitlines()]


def _build_partial_dependency_comparison_tabular(
    pairwise_comparisons: dict[str, Any],
    *,
    row_approach: str,
    column_approaches: list[str],
    stack_totals: bool = False,
    include_kappa: bool = False,
    row_label_width_macro: str | None = None,
) -> str:
    row_summary = _get_pairwise_summary(
        pairwise_comparisons,
        approach=row_approach,
        baseline=row_approach,
    )
    row_total = int(row_summary.get("approach_total", 0) or 0)

    label_formatter = (
        _format_bold_label_with_plain_total_stacked
        if stack_totals
        else _format_bold_label_with_plain_total
    )

    header_line = (
        " & ".join(
            [
                r"\diagbox{\textbf{$A$}}{\textbf{$B$}}",
                r"\textbf{Metric}",
                *[
                    label_formatter(
                        SHORT_LABELS[key],
                        int(
                            _get_pairwise_summary(
                                pairwise_comparisons,
                                approach=row_approach,
                                baseline=key,
                            ).get("baseline_total", 0)
                            or 0
                        ),
                    )
                    for key in column_approaches
                ],
            ]
        )
        + r" \\"
    )

    metric_values_by_baseline = [
        _build_cell(pairwise_comparisons.get(f"{row_approach}__vs__{baseline}", {}))
        for baseline in column_approaches
    ]

    row_label = (
        _format_fixed_width_stacked_label(
            SHORT_LABELS[row_approach], row_total, row_label_width_macro
        )
        if row_label_width_macro
        else label_formatter(SHORT_LABELS[row_approach], row_total)
    )
    metric_order = METRIC_ORDER + ([KAPPA_METRIC_LABEL] if include_kappa else [])
    body_lines = []
    for metric_index, metric_label in enumerate(metric_order):
        row_cells = []
        if metric_index == 0:
            row_cells.append(rf"\multirow{{{len(metric_order)}}}{{*}}{{{row_label}}}")
        else:
            row_cells.append("")
        row_cells.append(metric_label)
        for metric_values in metric_values_by_baseline:
            row_cells.append(metric_values[metric_label])
        body_lines.append("    " + " & ".join(row_cells) + r" \\")

    tabular_spec = "cc|" + ("c" * len(column_approaches))
    return "\n".join(
        [
            rf"\begin{{tabular}}{{{tabular_spec}}}",
            r"    \toprule",
            header_line,
            r"    \midrule%",
            *body_lines,
            r"    \bottomrule",
            r"\end{tabular}%",
        ]
    )


def export_dependency_comparison_latex_table(
    network_data: dict[str, Any],
    output_path: Path,
    *,
    tabcolsep_pt: int = LATEX_TABCOLSEP_PT,
) -> None:
    pairwise_comparisons = _build_pairwise_comparisons(network_data)
    totals = {
        key: int(
            _get_pairwise_summary(
                pairwise_comparisons, approach=key, baseline=key
            ).get("approach_total", 0)
            or 0
        )
        for key in APPROACH_ORDER
    }

    header_line = (
        " & ".join(
            [r"\diagbox{\textbf{$A$}}{\textbf{$B$}}", r"\textbf{Metric}"]
            + [
                _format_bold_label_with_plain_total_stacked(
                    SHORT_LABELS[key], totals[key]
                )
                for key in APPROACH_ORDER
            ]
        )
        + r" \\"
    )

    body_lines = []
    metric_order = METRIC_ORDER + [KAPPA_METRIC_LABEL]
    for approach in APPROACH_ORDER:
        metric_values_by_baseline = []
        for baseline in APPROACH_ORDER:
            comparison_key = f"{approach}__vs__{baseline}"
            comparison = pairwise_comparisons.get(comparison_key, {})
            metric_values = _build_cell(comparison)
            if baseline == approach:
                # Self-comparisons carry no information; de-emphasise them.
                metric_values = {
                    label: (
                        rf"\textcolor[gray]{{{DIAGONAL_GRAY_LEVEL}}}{{{value}}}"
                    )
                    for label, value in metric_values.items()
                }
            metric_values_by_baseline.append(metric_values)

        for metric_index, metric_label in enumerate(metric_order):
            row_cells = []
            if metric_index == 0:
                row_cells.append(
                    rf"\multirow{{{len(metric_order)}}}{{*}}{{{_format_bold_label_with_plain_total_stacked(SHORT_LABELS[approach], totals[approach])}}}"
                )
            else:
                row_cells.append("")
            row_cells.append(metric_label)
            for metric_values in metric_values_by_baseline:
                row_cells.append(metric_values[metric_label])
            body_lines.append("        " + " & ".join(row_cells) + r" \\")
        if approach != APPROACH_ORDER[-1]:
            body_lines.append(r"        \midrule%")

    latex_table = "\n".join(
        [
            "{%",
            r"    \setlength{\abovetopsep}{0pt}%",
            r"    \setlength{\belowbottomsep}{0pt}%",
            r"    \setlength{\aboverulesep}{0pt}%",
            r"    \setlength{\belowrulesep}{0pt}%",
            rf"    \setlength{{\tabcolsep}}{{{tabcolsep_pt}pt}}%",
            r"    \renewcommand{\arraystretch}{1.3}%",
            r"    \begin{tabular}{cc|ccc}",
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


def export_preamble_dependency_comparison_latex_table(
    network_data: dict[str, Any],
    output_path: Path,
    *,
    tabcolsep_pt: int = LATEX_TABCOLSEP_PT,
) -> None:
    pairwise_comparisons = _build_pairwise_comparisons(network_data)
    tabular_block = _build_partial_dependency_comparison_tabular(
        pairwise_comparisons,
        row_approach=PREAMBLE_EXTRACTED,
        column_approaches=PREAMBLE_ONLY_COLUMN_ORDER,
    )

    latex_table = "\n".join(
        [
            "{%",
            r"    \setlength{\abovetopsep}{0pt}%",
            r"    \setlength{\belowbottomsep}{0pt}%",
            r"    \setlength{\aboverulesep}{0pt}%",
            r"    \setlength{\belowrulesep}{0pt}%",
            rf"    \setlength{{\tabcolsep}}{{{tabcolsep_pt}pt}}%",
            r"    \renewcommand{\arraystretch}{1.3}%",
            *_indent_block(tabular_block),
            "}",
            "",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(latex_table, encoding="utf-8")


def export_preamble_plus_regex_llm_dependency_comparison_latex_table(
    network_data: dict[str, Any],
    output_path: Path,
    *,
    tabcolsep_pt: int = LATEX_TABCOLSEP_PT,
) -> None:
    pairwise_comparisons = _build_pairwise_comparisons(network_data)
    # Shared fixed width for the approach-label column so the two stacked
    # tabulars align exactly; sized to the widest label line of either block.
    width_macro = r"\depCmpApproachColWidth"
    width_setup_lines = _build_label_width_setup(
        width_macro,
        [
            rf"\textbf{{{_latex_escape(SHORT_LABELS[approach])}}}"
            for approach in (PREAMBLE_EXTRACTED, BODY_EXTRACTED_REGEX)
        ],
    )
    top_tabular_block = _build_partial_dependency_comparison_tabular(
        pairwise_comparisons,
        row_approach=PREAMBLE_EXTRACTED,
        column_approaches=PREAMBLE_ONLY_COLUMN_ORDER,
        stack_totals=True,
        include_kappa=True,
        row_label_width_macro=width_macro,
    )
    bottom_tabular_block = _build_partial_dependency_comparison_tabular(
        pairwise_comparisons,
        row_approach=BODY_EXTRACTED_REGEX,
        column_approaches=REGEX_VS_LLM_COLUMN_ORDER,
        stack_totals=True,
        include_kappa=True,
        row_label_width_macro=width_macro,
    )

    # The two blocks are rows of an outer one-column tabular (not minipages
    # separated by \par) so the whole table stays a single vertical box:
    # consumers wrap it in \resizebox, which is an \hbox where \par is inert
    # and stacked minipages would silently end up side by side.
    latex_table = "\n".join(
        [
            "{%",
            r"    \setlength{\abovetopsep}{0pt}%",
            r"    \setlength{\belowbottomsep}{0pt}%",
            r"    \setlength{\aboverulesep}{0pt}%",
            r"    \setlength{\belowrulesep}{0pt}%",
            rf"    \setlength{{\tabcolsep}}{{{tabcolsep_pt}pt}}%",
            r"    \renewcommand{\arraystretch}{1.3}%",
            *width_setup_lines,
            r"    \begin{tabular}{@{}l@{}}",
            *_indent_block(top_tabular_block),
            r"    \\[8pt]",
            *_indent_block(bottom_tabular_block),
            r"    \end{tabular}%",
            "}",
            "",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(latex_table, encoding="utf-8")
