from pathlib import Path
from typing import Any, Dict, List, Tuple

from analysis.dependencies.constants import (
    BODY_EXTRACTED_LLM,
    BODY_EXTRACTED_REGEX,
    DEPENDENCY_APPROACH_SHORT_LABELS,
    PREAMBLE_EXTRACTED,
)


LATEX_TABCOLSEP_PT = 4
LATEX_ARRAYSTRETCH = 1.15
APPROACH_ORDER = [PREAMBLE_EXTRACTED, BODY_EXTRACTED_REGEX, BODY_EXTRACTED_LLM]
SHORT_LABELS = DEPENDENCY_APPROACH_SHORT_LABELS

METRICS: List[Tuple[str, str]] = [
    ("in_degree",           "In Deg."),
    ("weighted_eigenvector","W. EV"),
    ("pagerank",            "PageRank"),
    ("betweenness",         "BC"),
]

TOP_N = 5
TITLE_CHARS = 7
TITLE_CHARS_UPPER = 5  # uppercase letters are ~1.4x wider; 10/1.4 ≈ 7

# Colors cycled through for cross-metric BIPs within each approach block.
# Each distinct BIP that spans >1 metric column gets the next color; resets per block.
HIGHLIGHT_COLORS = [
    r"red!70!black",
    r"blue!70!black",
    "teal",
    r"orange!80!black",
    "violet",
    r"green!55!black",
    r"brown!80!black",
]

# Each metric occupies 3 sub-columns: ID (l), title (l), value (r).
# A thin space separates ID from title; a thicker medium space separates title from value.
_SUB = r"l@{\,}l@{\quad}r"
_TABULAR_SPEC = r"c@{\;}c|" + "|".join(_SUB for _ in METRICS)


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


def _title_substr(title: str) -> str:
    """Use a shorter limit for predominantly-uppercase titles to match visual width."""
    alpha = [c for c in title if c.isalpha()]
    if alpha and sum(1 for c in alpha if c.isupper()) / len(alpha) > 0.6:
        return title[:TITLE_CHARS_UPPER].strip()
    return title[:TITLE_CHARS].strip()


def _colored(text: str, color: str | None) -> str:
    return rf"\textcolor{{{color}}}{{{text}}}" if color else text


def _bip(bip_id: str, color: str | None = None) -> str:
    return rf"\BIPC{{{bip_id}}}{{{color or 'black'}}}"


def _colored_title(text: str, color: str | None = None) -> str:
    return _colored(text, color)


def _rank_cell(rank: int) -> str:
    return r"\textit{\textcolor{gray}{(" + str(rank) + r")}}"


def _format_value(value: float, metric: str) -> str:
    if metric == "in_degree":
        return str(int(value))
    if metric in ("weighted_eigenvector", "pagerank"):
        return f"{value:.3f}"
    return f"{value:.4f}"


def _top5(per_bip: List[Dict], metric: str) -> List[Dict]:
    return sorted(per_bip, key=lambda r: r.get(metric, 0), reverse=True)[:TOP_N]


def _build_header_line() -> str:
    cells = [r"\multicolumn{2}{c|}{\textbf{Approach}}"]
    for i, (_, label) in enumerate(METRICS):
        col_format = "c|" if i < len(METRICS) - 1 else "c"
        cells.append(rf"\multicolumn{{3}}{{{col_format}}}{{\textbf{{{label}}}}}")
    return " & ".join(cells) + r" \\"


def _build_approach_rows(
    approach: str,
    per_bip: List[Dict],
) -> List[str]:
    tops = {metric: _top5(per_bip, metric) for metric, _ in METRICS}

    # Identify cross-metric BIPs (appear in >1 metric column) in first-appearance order.
    id_metric_count: Dict[str, int] = {}
    for metric, _ in METRICS:
        for entry in tops[metric]:
            bip_id = str(entry["id"])
            id_metric_count[bip_id] = id_metric_count.get(bip_id, 0) + 1

    ordered_cross: List[str] = []
    seen: set = set()
    for metric, _ in METRICS:
        for entry in tops[metric]:
            bip_id = str(entry["id"])
            if id_metric_count[bip_id] > 1 and bip_id not in seen:
                seen.add(bip_id)
                ordered_cross.append(bip_id)

    color_map: Dict[str, str] = {
        bip_id: HIGHLIGHT_COLORS[i % len(HIGHLIGHT_COLORS)]
        for i, bip_id in enumerate(ordered_cross)
    }

    rows = []
    for rank_idx in range(TOP_N):
        cells = []
        if rank_idx == 0:
            cells.append(
                rf"\multirow{{{TOP_N}}}{{*}}{{\textbf{{{SHORT_LABELS[approach]}}}}}"
            )
        else:
            cells.append("")
        cells.append(_rank_cell(rank_idx + 1))
        for metric, _ in METRICS:
            entry = tops[metric][rank_idx]
            raw_id = str(entry["id"])
            color = color_map.get(raw_id)
            bip_cell = _bip(raw_id, color=color)
            title = _colored_title(_latex_escape(_title_substr(entry.get("title") or "")) + r"\mydots", color=color)
            value = _format_value(entry.get(metric, 0), metric)
            cells += [bip_cell, title, value]
        rows.append("        " + " & ".join(cells) + r" \\")
    return rows


def export_centrality_top5_latex_table(
    dep_metrics: Dict[str, Any],
    output_path: Path,
    *,
    tabcolsep_pt: float = LATEX_TABCOLSEP_PT,
) -> None:
    body_lines = []
    for i, approach in enumerate(APPROACH_ORDER):
        per_bip = dep_metrics["by_approach"][approach]["per_bip"]
        body_lines.extend(_build_approach_rows(approach, per_bip))
        if i < len(APPROACH_ORDER) - 1:
            body_lines.append(r"        \midrule%")

    header_line = _build_header_line()

    latex_table = "\n".join(
        [
            "{%",
            r"    \newcommand\mydots{\hbox to 1em{.\hss.\hss.}}%",
            r"    \setlength{\abovetopsep}{0pt}%",
            r"    \setlength{\belowbottomsep}{0pt}%",
            r"    \setlength{\aboverulesep}{0pt}%",
            r"    \setlength{\belowrulesep}{0pt}%",
            rf"    \setlength{{\tabcolsep}}{{{tabcolsep_pt}pt}}%",
            rf"    \renewcommand{{\arraystretch}}{{{LATEX_ARRAYSTRETCH}}}%",
            rf"    \begin{{tabular}}{{{_TABULAR_SPEC}}}",
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
