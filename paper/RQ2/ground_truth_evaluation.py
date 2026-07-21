"""Ground-truth evaluation of the dependency-extraction approaches.

Python port of the React dashboard evaluation
(react/src/dependencyGroundTruthEvaluation.js) in Exact Type match mode: a
predicted edge only counts as a true positive when the directed pair exists in
the curated ground truth AND the approach subtype's mapped relation type
equals the curated relation type. Each approach is scored only against the
gold edges of the types it is mapped to detect, and only for source proposals
inside the reviewed benchmark scope.

Two Mode mappings are provided (mirroring the "Mode" column in
dependency_type_mapping_table.py):
  - ETA_TYPE_MAPPING ("Edge type agnostic"): a subtype counts as a match
    against any ground-truth relation type on the same directed edge, via the
    GT_TYPE_ALL wildcard target.
  - DOE_TYPE_MAPPING ("Dependency-only edges"): a subtype only counts as a
    match when the ground truth records that edge as depends_on.
"""

from pathlib import Path

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np

from analysis.dependencies.constants import (
    BODY_EXTRACTED_LLM,
    BODY_EXTRACTED_REGEX,
    DEPENDENCY_APPROACH_SHORT_LABELS,
    GROUND_TRUTH_CURATED,
    PREAMBLE_EXTRACTED,
)
from paper.config import (
    FIGURE_TITLE_FONT_SIZE,
    LEGEND_FONT_SIZE,
    SUBPLOT_TITLE_FONT_SIZE,
)
from paper.plot_colors import ORDERED_PLOT_PALETTE
from paper.RQ3._plotting import (
    bar_style,
    despine,
    match_axis_label_fontsize,
    save_figure,
)

EVALUATED_APPROACHES = [
    PREAMBLE_EXTRACTED,
    BODY_EXTRACTED_REGEX,
    BODY_EXTRACTED_LLM,
]

# Sentinel target meaning "match any ground-truth type" (mirrors GT_TYPE_ALL in
# react/src/dependencyGroundTruthEvaluation.js): a subtype mapped to this
# target counts as a true positive against whichever relation type(s) the
# ground truth actually recorded for that directed pair.
GT_TYPE_ALL = "*"

ETA_TYPE_MAPPING = {
    PREAMBLE_EXTRACTED: {
        "requires": GT_TYPE_ALL,
    },
    BODY_EXTRACTED_REGEX: {"reference": GT_TYPE_ALL},
    BODY_EXTRACTED_LLM: {"implicit_dependency": GT_TYPE_ALL},
}

DOE_TYPE_MAPPING = {
    PREAMBLE_EXTRACTED: {"requires": "depends_on"},
    BODY_EXTRACTED_REGEX: {"reference": "depends_on"},
    BODY_EXTRACTED_LLM: {"implicit_dependency": "depends_on"},
}

COUNT_SERIES = [
    ("tp", "TP", ORDERED_PLOT_PALETTE[2]),
    ("fp", "FP", ORDERED_PLOT_PALETTE[1]),
    ("fn", "FN", ORDERED_PLOT_PALETTE[0]),
]

SCORE_SERIES = [
    ("precision", "Precision", ORDERED_PLOT_PALETTE[4]),
    ("recall", "Recall", ORDERED_PLOT_PALETTE[6]),
    ("f1", "F1", ORDERED_PLOT_PALETTE[5]),
]

# Sized for a single paper column: side by side like the other two-panel
# figures (e.g. plot_authorship_overview), but narrower/shorter to match a
# single-column width instead of a two-column-spanning one. Narrower than
# before since rotating the value labels 90 degrees frees up horizontal room.
EVALUATION_FIGSIZE = (5.6, 3.5)
# Two-column-width, single-row layout combining both modes into four panels
# (ETA counts, ETA scores, DOE counts, DOE scores) for a two-column print.
# Per-panel width matches the solo figure's (EVALUATION_FIGSIZE width / 2) so
# bars, gaps, and tick labels keep the same proportions as the solo plots.
COMBINED_EVALUATION_FIGSIZE = (11.0, 3)
# A bit more breathing room than the solo defaults (BAR_GROUP_WIDTH/
# BAR_SLOT_FILL below) between bars within a group and between groups.
COMBINED_BAR_GROUP_WIDTH = 0.8
COMBINED_BAR_SLOT_FILL = 0.8
BAR_GROUP_WIDTH = 0.9
# Fraction of each within-group slot filled by the bar; the rest is spacing.
BAR_SLOT_FILL = 0.9
# Extra room left/right of the outermost bar groups, in x-axis data units;
# just enough to clear the outermost bars without leaving a big empty margin.
AXIS_EDGE_MARGIN = 0.45


def _normalize_relation_type(relation_type) -> str:
    return str(relation_type or "").strip().lower()


def _directed_pair_key(edge: dict) -> str:
    source = str(edge.get("source") or "").strip()
    target = str(edge.get("target") or "").strip()
    return f"{source}->{target}" if source and target else ""


def _typed_edge_key(edge: dict, type_label: str) -> str:
    base_key = _directed_pair_key(edge)
    relation_type = _normalize_relation_type(type_label)
    return f"{base_key}:::{relation_type}" if base_key and relation_type else base_key


def _edges_by_method(network_data: dict, extraction_method: str) -> list[dict]:
    return [
        edge
        for edge in network_data.get("dependency_edges", [])
        if edge.get("extraction_method") == extraction_method
    ]


def _summarize(predicted_keys: set[str], gold_keys: set[str]) -> dict[str, float]:
    tp = len(predicted_keys & gold_keys)
    fp = len(predicted_keys) - tp
    fn = len(gold_keys - predicted_keys)
    precision = tp / (tp + fp) if tp + fp > 0 else 0.0
    recall = tp / (tp + fn) if tp + fn > 0 else 0.0
    f1 = (
        (2 * precision * recall) / (precision + recall)
        if precision + recall > 0
        else 0.0
    )
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def build_exact_type_evaluation(
    network_data: dict,
    type_mapping: dict[str, dict[str, str]],
) -> dict:
    mapping = type_mapping
    reviewed_source_keys = {
        str(entry.get("ip") or "").strip()
        for entry in network_data.get("ground_truth_reviewed_ips", [])
        if str(entry.get("ip") or "").strip()
    }
    if not reviewed_source_keys:
        raise ValueError(
            "Ground-truth evaluation requires reviewed IPs in the network artifact."
        )

    gold_edges = _edges_by_method(network_data, GROUND_TRUTH_CURATED)
    gold_keys_by_type: dict[str, set[str]] = {}
    # Directed pair -> set of gold relation types, used to resolve GT_TYPE_ALL
    # ("match any type") targets to the type(s) actually recorded for that pair.
    gold_types_by_pair: dict[str, set[str]] = {}
    all_gold_types: set[str] = set()
    for edge in gold_edges:
        relation_type = _normalize_relation_type(edge.get("relation_type"))
        key = _typed_edge_key(edge, relation_type)
        if key:
            gold_keys_by_type.setdefault(relation_type, set()).add(key)
        if relation_type:
            all_gold_types.add(relation_type)
            pair = _directed_pair_key(edge)
            if pair:
                gold_types_by_pair.setdefault(pair, set()).add(relation_type)

    approaches = []
    for approach in EVALUATED_APPROACHES:
        included = {
            _normalize_relation_type(subtype): _normalize_relation_type(target)
            for subtype, target in mapping.get(approach, {}).items()
        }
        predicted_keys: set[str] = set()
        for edge in _edges_by_method(network_data, approach):
            if str(edge.get("source") or "").strip() not in reviewed_source_keys:
                continue
            relation_type = _normalize_relation_type(edge.get("relation_type"))
            if relation_type not in included:
                continue
            target = included[relation_type]
            if target != GT_TYPE_ALL:
                predicted_keys.add(_typed_edge_key(edge, target))
                continue
            # A wildcard-mapped subtype matches whichever type(s) the ground
            # truth recorded for this directed pair, or (if the pair isn't in
            # the ground truth at all) the untyped pair, so it still counts as
            # a false positive rather than silently vanishing.
            pair = _directed_pair_key(edge)
            gold_types = gold_types_by_pair.get(pair)
            if gold_types:
                predicted_keys.update(_typed_edge_key(edge, t) for t in gold_types)
            else:
                predicted_keys.add(pair)
        predicted_keys.discard("")

        # Score only against the gold edges of the relation types this approach
        # is mapped to detect, so it is not penalised for types it never
        # targets; a wildcard target widens this to every curated gold type.
        targeted_types: set[str] = set()
        for target in included.values():
            if target == GT_TYPE_ALL:
                targeted_types |= all_gold_types
            else:
                targeted_types.add(target)
        targeted_gold_keys = set().union(
            *(gold_keys_by_type.get(target, set()) for target in targeted_types)
        )
        approaches.append(
            {
                "approach": approach,
                "label": DEPENDENCY_APPROACH_SHORT_LABELS.get(approach, approach),
                **_summarize(predicted_keys, targeted_gold_keys),
            }
        )

    return {
        "reviewed_proposal_count": len(reviewed_source_keys),
        "gold_edge_count": sum(len(keys) for keys in gold_keys_by_type.values()),
        "approaches": approaches,
    }


def _format_combined_score_label(value: float) -> str:
    text = f"{value:.2f}"
    return "1.0" if text == "1.00" else text.lstrip("0") or "0"


def _grouped_bar_positions(
    group_count: int, series_count: int, *, group_width: float = BAR_GROUP_WIDTH
) -> tuple[np.ndarray, float]:
    bar_width = group_width / series_count
    group_positions = np.arange(group_count, dtype=float)
    return group_positions, bar_width


def _draw_grouped_bars(
    axis,
    rows: list[dict],
    series: list[tuple[str, str, str]],
    *,
    title: str,
    value_formatter,
    label_offset: float,
    group_width: float = BAR_GROUP_WIDTH,
    slot_fill: float = BAR_SLOT_FILL,
    axis_edge_margin: float = AXIS_EDGE_MARGIN,
    label_rotation: float = 90,
) -> None:
    group_positions, bar_width = _grouped_bar_positions(
        len(rows), len(series), group_width=group_width
    )
    for series_index, (key, label, color) in enumerate(series):
        offsets = group_positions + (series_index - (len(series) - 1) / 2) * bar_width
        values = [float(row[key]) for row in rows]
        axis.bar(
            offsets,
            values,
            width=bar_width * slot_fill,
            zorder=2,
            label=label,
            **bar_style(color),
        )
        for x_position, value in zip(offsets, values, strict=True):
            text = axis.text(
                x_position,
                value + label_offset,
                value_formatter(value),
                ha="center",
                va="bottom",
                rotation=label_rotation,
                fontsize=8,
                zorder=5,
            )
            text.set_path_effects(
                [
                    pe.Stroke(linewidth=2.2, foreground="white", alpha=0.9),
                    pe.Normal(),
                ]
            )

    # The title gets extra padding so the legend fits between it and the axes.
    axis.set_title(title, pad=24, fontsize=SUBPLOT_TITLE_FONT_SIZE)
    axis.set_xticks(group_positions)
    axis.set_xticklabels([row["label"] for row in rows])
    axis.set_xlim(-axis_edge_margin, len(rows) - 1 + axis_edge_margin)
    axis.grid(axis="y", alpha=0.35)
    axis.grid(axis="x", visible=False)
    axis.legend(
        frameon=False,
        fontsize=LEGEND_FONT_SIZE,
        ncol=len(series),
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        borderaxespad=0.2,
        columnspacing=0.9,
        handlelength=1.2,
        handletextpad=0.4,
    )
    match_axis_label_fontsize(axis)
    despine(axis)


def _plot_ground_truth_evaluation(
    network_data: dict,
    output_path: Path,
    snapshot_label: str,
    *,
    type_mapping: dict[str, dict[str, str]],
    mode_title: str,
) -> dict:
    evaluation = build_exact_type_evaluation(network_data, type_mapping=type_mapping)
    rows = evaluation["approaches"]

    figure, (axis_counts, axis_scores) = plt.subplots(
        1,
        2,
        figsize=EVALUATION_FIGSIZE,
    )

    count_max = max(float(row[key]) for row in rows for key, _, _ in COUNT_SERIES)
    _draw_grouped_bars(
        axis_counts,
        rows,
        COUNT_SERIES,
        title="(a) Edge Match Counts",
        value_formatter=lambda value: f"{value:.0f}",
        label_offset=max(count_max * 0.015, 0.15),
    )
    axis_counts.set_ylabel("# Edges")
    axis_counts.set_ylim(0, count_max * 1.18 if count_max > 0 else 1)

    _draw_grouped_bars(
        axis_scores,
        rows,
        SCORE_SERIES,
        title="(b) Quality Metrics",
        value_formatter=lambda value: f"{value:.2f}",
        label_offset=0.015,
    )
    axis_scores.set_ylabel("Score")
    axis_scores.set_ylim(0, 1.12)
    axis_scores.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    axis_scores.set_yticklabels(["0.00", "0.25", "0.50", "0.75", "1.00"])
    match_axis_label_fontsize(axis_scores)

    # At single-column width the full title doesn't fit on one line, so it
    # wraps. tight_layout() first sizes the axes/legend/tick labels normally;
    # subplots_adjust then only pulls the top down to clear the two-line
    # suptitle (a plain tight_layout `rect` reserves that band far more
    # generously than the title actually needs, leaving a large blank gap).
    figure.tight_layout()
    figure.subplots_adjust(top=0.66, wspace=0.4)
    figure.suptitle(
        f"Ground-Truth Evaluation\n{mode_title} ({snapshot_label})",
        y=0.99,
        fontsize=FIGURE_TITLE_FONT_SIZE,
    )
    save_figure(figure, output_path)
    return evaluation


def plot_ground_truth_evaluation_eta(
    network_data: dict,
    output_path: Path,
    snapshot_label: str,
    type_mapping: dict[str, dict[str, str]] | None = None,
) -> dict:
    """Edge type agnostic (ETA): scores a match against any ground-truth
    relation type on the same directed edge."""
    return _plot_ground_truth_evaluation(
        network_data,
        output_path,
        snapshot_label,
        type_mapping=type_mapping or ETA_TYPE_MAPPING,
        mode_title="Edge Type Agnostic (ETA)",
    )


def plot_ground_truth_evaluation_combined(
    network_data: dict,
    output_path: Path,
    snapshot_label: str,
    eta_type_mapping: dict[str, dict[str, str]] | None = None,
    doe_type_mapping: dict[str, dict[str, str]] | None = None,
) -> dict:
    """Single two-column-width figure combining the ETA and DOE ground-truth
    evaluations into four side-by-side panels: ETA counts, ETA scores, DOE
    counts, DOE scores. Meant for a two-column print, replacing the two
    separate single-column figures."""
    eta_evaluation = build_exact_type_evaluation(
        network_data, type_mapping=eta_type_mapping or ETA_TYPE_MAPPING
    )
    doe_evaluation = build_exact_type_evaluation(
        network_data, type_mapping=doe_type_mapping or DOE_TYPE_MAPPING
    )

    figure, (
        axis_eta_counts,
        axis_eta_scores,
        axis_doe_counts,
        axis_doe_scores,
    ) = plt.subplots(1, 4, figsize=COMBINED_EVALUATION_FIGSIZE)

    panels = (
        (axis_eta_counts, axis_eta_scores, eta_evaluation, "ETA"),
        (axis_doe_counts, axis_doe_scores, doe_evaluation, "DOE"),
    )
    letters = iter("abcd")
    for axis_counts, axis_scores, evaluation, mode_label in panels:
        rows = evaluation["approaches"]

        count_max = max(float(row[key]) for row in rows for key, _, _ in COUNT_SERIES)
        _draw_grouped_bars(
            axis_counts,
            rows,
            COUNT_SERIES,
            title=f"({next(letters)}) {mode_label} Counts",
            value_formatter=lambda value: f"{value:.0f}",
            label_offset=max(count_max * 0.015, 0.15),
            group_width=COMBINED_BAR_GROUP_WIDTH,
            slot_fill=COMBINED_BAR_SLOT_FILL,
            label_rotation=0,
        )
        axis_counts.set_ylabel("# Edges")
        axis_counts.set_ylim(0, count_max * 1.18 if count_max > 0 else 1)

        _draw_grouped_bars(
            axis_scores,
            rows,
            SCORE_SERIES,
            title=f"({next(letters)}) {mode_label} Scores",
            value_formatter=_format_combined_score_label,
            label_offset=0.015,
            group_width=COMBINED_BAR_GROUP_WIDTH,
            slot_fill=COMBINED_BAR_SLOT_FILL,
            label_rotation=0,
        )
        axis_scores.set_ylabel("Score")
        axis_scores.set_ylim(0, 1.12)
        axis_scores.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
        axis_scores.set_yticklabels(["0.00", "0.25", "0.50", "0.75", "1.00"])
        match_axis_label_fontsize(axis_scores)

    figure.tight_layout()
    figure.subplots_adjust(top=0.72, wspace=0.4)
    figure.suptitle(
        f"Ground-Truth Evaluation ({snapshot_label})",
        y=0.99,
        fontsize=FIGURE_TITLE_FONT_SIZE,
    )
    save_figure(figure, output_path)
    return {"eta": eta_evaluation, "doe": doe_evaluation}


def plot_ground_truth_evaluation_doe(
    network_data: dict,
    output_path: Path,
    snapshot_label: str,
    type_mapping: dict[str, dict[str, str]] | None = None,
) -> dict:
    """Dependency-only edges (DOE): scores a match only against depends_on."""
    return _plot_ground_truth_evaluation(
        network_data,
        output_path,
        snapshot_label,
        type_mapping=type_mapping or DOE_TYPE_MAPPING,
        mode_title="Dependency-Only Edges (DOE)",
    )
