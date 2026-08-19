from pathlib import Path
from typing import Any

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

METRICS: list[tuple[str, str]] = [
    ("in_degree", "In-Degree"),
    ("weighted_eigenvector", "WEV"),
    ("pagerank", "PageRank"),
    ("betweenness", "BC"),
]

TOP_N = 5
TITLE_CHARS = 9
TITLE_CHARS_UPPER = 7  # uppercase letters are ~1.4x wider; 10/1.4 ≈ 7

# Foreground and background colors are each individually distinctive to the
# eye and deliberately spread across the hue wheel (no two warm hues, e.g.
# no orange alongside red) so no pair of badges reads as "the same color
# family." HIGHLIGHT_COLOR_PAIRS below is the full permutation set built
# from them, giving far more distinct (fg, bg) badges than either list alone.
FOREGROUND_COLORS: list[str] = [
    "red!75!black",
    "blue!70!black",
    "green!55!black",
    "violet!70!black",
    "teal!85!black",
]
BACKGROUND_COLORS: list[str] = [
    "red!12",
    "blue!10",
    "green!13",
    "violet!12",
    "teal!12",
]


def _permuted_highlight_color_pairs() -> list[tuple[str, str]]:
    """Ranked badge list, most-legible/most-distinct first:

    Round 0 — light badges: dark text (FOREGROUND_COLORS[i]) on a light tint
    of the same hue (BACKGROUND_COLORS[i]), one per hue.
    Round 1 — dark badges: white text on a solid version of the same hue
    (FOREGROUND_COLORS[i] reused as the background), one per hue. Same 5
    hues as round 0 but inverted contrast, so still maximally distinct from
    their round-0 neighbors.
    Remaining rounds — light cross-hue combos, cycling every foreground
    color once per round (shifted background), so no two picks in a row
    ever share a foreground color.

    This way the most-frequent BIPs (which rank first) get the 10 cleanest,
    most-contrasted badges before anything repeats a hue+style combo.
    """
    n = len(FOREGROUND_COLORS)
    pairs = [(FOREGROUND_COLORS[i], BACKGROUND_COLORS[i]) for i in range(n)]
    pairs += [("white", FOREGROUND_COLORS[i]) for i in range(n)]
    pairs += [
        (FOREGROUND_COLORS[i], BACKGROUND_COLORS[(i + shift) % n])
        for shift in range(1, n)
        for i in range(n)
    ]
    return pairs


# BIPs that recur across the table are assigned one badge each, in
# descending order of how many cells they appear in — the most-frequent BIP
# gets HIGHLIGHT_COLOR_PAIRS[0], the next gets [1], and so on (1:1 mapping).
HIGHLIGHT_COLOR_PAIRS: list[tuple[str, str]] = _permuted_highlight_color_pairs()

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
    # \BIPC already prepends "BIP" itself, so strip the "<source>:" prefix
    # (e.g. "bips:32" -> "32") or it renders as "BIPbips:32".
    display_id = bip_id.split(":", 1)[-1]
    return rf"\BIPC{{{display_id}}}{{{color or 'black'}}}"


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


def _top5(per_bip: list[dict], metric: str) -> list[dict]:
    return sorted(per_bip, key=lambda r: r.get(metric, 0), reverse=True)[:TOP_N]


def _build_header_line() -> str:
    cells = [r"\multicolumn{2}{c|}{\textbf{Approach}}"]
    for i, (_, label) in enumerate(METRICS):
        col_format = "c|" if i < len(METRICS) - 1 else "c"
        cells.append(rf"\multicolumn{{3}}{{{col_format}}}{{\textbf{{{label}}}}}")
    return " & ".join(cells) + r" \\"


def _build_global_color_map(
    dep_metrics: dict[str, Any], approach_order: list[str]
) -> dict[str, tuple[str, str]]:
    """Assign a (fg, bg) badge to every BIP that recurs in >1 cell anywhere in
    the table, ranked by how many cells it appears in (most first), so it
    keeps the same identity everywhere and the busiest BIP gets the cleanest
    badge — rather than being recolored independently per approach block."""
    tops_by_approach = {
        approach: {
            metric: _top5(dep_metrics["by_approach"][approach]["per_bip"], metric)
            for metric, _ in METRICS
        }
        for approach in approach_order
    }

    cell_count: dict[str, int] = {}
    first_seen_order: dict[str, int] = {}
    for approach in approach_order:
        for metric, _ in METRICS:
            for entry in tops_by_approach[approach][metric]:
                bip_id = str(entry["id"])
                if bip_id not in cell_count:
                    first_seen_order[bip_id] = len(first_seen_order)
                cell_count[bip_id] = cell_count.get(bip_id, 0) + 1

    recurring = sorted(
        (bip_id for bip_id, count in cell_count.items() if count > 1),
        key=lambda bip_id: (-cell_count[bip_id], first_seen_order[bip_id]),
    )
    return {
        bip_id: HIGHLIGHT_COLOR_PAIRS[i % len(HIGHLIGHT_COLOR_PAIRS)]
        for i, bip_id in enumerate(recurring)
    }


def _build_approach_rows(
    approach: str,
    per_bip: list[dict],
    color_map: dict[str, tuple[str, str]],
    badge_id_contents: list[str],
    badge_title_contents: list[str],
) -> list[str]:
    tops = {metric: _top5(per_bip, metric) for metric, _ in METRICS}

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
            fg, bg = color_map.get(raw_id, (None, None))
            bip_text = _bip(raw_id, color=fg)
            title_text = _colored_title(
                _latex_escape(_title_substr(entry.get("title") or "")) + r"\mydots",
                color=fg,
            )
            value = _format_value(entry.get(metric, 0), metric)
            if bg:
                # Merge the ID and title sub-columns into one spanning cell so
                # the badge is a single continuous block, not two separate
                # \colorbox regions with a gap between them — while keeping the
                # same internal left-aligned id/title layout as the plain (l@
                # {\,}l) columns: each piece sits in its own fixed-width slot
                # (\BadgeIdWidth / \BadgeTitleWidth, measured across every
                # badge's own content in export_centrality_top5_latex_table),
                # so ids line up under ids and titles line up under titles.
                badge_id_contents.append(bip_text)
                badge_title_contents.append(title_text)
                cells.append(
                    rf"\multicolumn{{2}}{{l}}{{\colorbox{{{bg}}}{{\makebox[\BadgeIdWidth][l]{{{bip_text}}}\,\makebox[\BadgeTitleWidth][l]{{{title_text}}}}}}}"
                )
            else:
                cells += [bip_text, title_text]
            cells.append(value)
        rows.append("        " + " & ".join(cells) + r" \\")
    return rows


def export_centrality_top5_latex_table(
    dep_metrics: dict[str, Any],
    output_path: Path,
    *,
    tabcolsep_pt: float = LATEX_TABCOLSEP_PT,
) -> None:
    color_map = _build_global_color_map(dep_metrics, APPROACH_ORDER)

    badge_id_contents: list[str] = []
    badge_title_contents: list[str] = []
    body_lines = []
    for i, approach in enumerate(APPROACH_ORDER):
        per_bip = dep_metrics["by_approach"][approach]["per_bip"]
        body_lines.extend(
            _build_approach_rows(
                approach, per_bip, color_map, badge_id_contents, badge_title_contents
            )
        )
        if i < len(APPROACH_ORDER) - 1:
            body_lines.append(r"        \midrule%")

    header_line = _build_header_line()

    # Measure each badge's id and title content width in LaTeX itself (font
    # metrics for \texttt id vs. regular-weight title aren't predictable from
    # Python) and take the max of each as \BadgeIdWidth / \BadgeTitleWidth, so
    # every badge gets the same internal id/title layout as the plain
    # (unhighlighted) columns — ids line up under ids, titles under titles —
    # regardless of id digit count or title length.
    def _width_measure_lines(length_name: str, contents: list[str]) -> list[str]:
        lines = [
            rf"    \newlength{{\{length_name}}}%",
            rf"    \setlength{{\{length_name}}}{{0pt}}%",
        ]
        for content in dict.fromkeys(contents):
            lines.append(rf"    \settowidth{{\BadgeWidthTmp}}{{{content}}}%")
            lines.append(
                rf"    \ifdim\BadgeWidthTmp>\{length_name} \setlength{{\{length_name}}}{{\BadgeWidthTmp}}\fi%"
            )
        return lines

    badge_width_lines = [r"    \newlength{\BadgeWidthTmp}%"]
    badge_width_lines += _width_measure_lines("BadgeIdWidth", badge_id_contents)
    badge_width_lines += _width_measure_lines("BadgeTitleWidth", badge_title_contents)

    latex_table = "\n".join(
        [
            "{%",
            r"    \newcommand\mydots{\hbox to 1em{.\hss.\hss.}}%",
            r"    \setlength{\abovetopsep}{0pt}%",
            r"    \setlength{\belowbottomsep}{0pt}%",
            r"    \setlength{\aboverulesep}{0pt}%",
            r"    \setlength{\belowrulesep}{0pt}%",
            r"    \setlength{\fboxsep}{1.5pt}%",
            *badge_width_lines,
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
