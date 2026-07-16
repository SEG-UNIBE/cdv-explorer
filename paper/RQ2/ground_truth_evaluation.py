"""Ground-truth evaluation of the dependency-extraction approaches.

Python port of the React dashboard evaluation
(react/src/dependencyGroundTruthEvaluation.js) in Exact Type match mode:
a predicted edge only counts as a true positive when the directed pair exists
in the curated ground truth AND the approach subtype's mapped relation type
equals the curated relation type. Each approach is scored only against the
gold edges of the types it is mapped to detect, and only for source proposals
inside the reviewed benchmark scope.
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
from paper.config import FIGURE_TITLE_FONT_SIZE, SUBPLOT_TITLE_FONT_SIZE
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

# Default subtype -> ground-truth relation-type mapping, mirroring the
# dashboard's Exact Type defaults (relation ontology + preferred GT targets).
DEFAULT_TYPE_MAPPING = {
    PREAMBLE_EXTRACTED: {
        "requires": "depends_on",
        "replaces": "supersedes",
        "proposed_replacement": "superseded_by",
    },
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

EVALUATION_FIGSIZE = (5, 5)
BAR_GROUP_WIDTH = 0.75
# Fraction of each within-group slot filled by the bar; the rest is spacing.
BAR_SLOT_FILL = 0.75


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
    type_mapping: dict[str, dict[str, str]] | None = None,
) -> dict:
    mapping = type_mapping or DEFAULT_TYPE_MAPPING
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
    for edge in gold_edges:
        relation_type = _normalize_relation_type(edge.get("relation_type"))
        key = _typed_edge_key(edge, relation_type)
        if key:
            gold_keys_by_type.setdefault(relation_type, set()).add(key)

    approaches = []
    for approach in EVALUATED_APPROACHES:
        included = {
            _normalize_relation_type(subtype): _normalize_relation_type(target)
            for subtype, target in mapping.get(approach, {}).items()
        }
        predicted_keys = {
            _typed_edge_key(edge, included[relation_type])
            for edge in _edges_by_method(network_data, approach)
            if str(edge.get("source") or "").strip() in reviewed_source_keys
            and (relation_type := _normalize_relation_type(edge.get("relation_type")))
            in included
        }
        predicted_keys.discard("")
        # Score only against the gold edges of the relation types this approach
        # is mapped to detect, so it is not penalised for types it never targets.
        targeted_gold_keys = set().union(
            *(gold_keys_by_type.get(target, set()) for target in included.values())
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


def _grouped_bar_positions(
    group_count: int, series_count: int
) -> tuple[np.ndarray, float]:
    bar_width = BAR_GROUP_WIDTH / series_count
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
) -> None:
    group_positions, bar_width = _grouped_bar_positions(len(rows), len(series))
    for series_index, (key, label, color) in enumerate(series):
        offsets = group_positions + (series_index - (len(series) - 1) / 2) * bar_width
        values = [float(row[key]) for row in rows]
        axis.bar(
            offsets,
            values,
            width=bar_width * BAR_SLOT_FILL,
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
    axis.set_xlim(-0.6, len(rows) - 0.4)
    axis.grid(axis="y", alpha=0.35)
    axis.grid(axis="x", visible=False)
    axis.legend(
        frameon=False,
        fontsize=8,
        ncol=len(series),
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        borderaxespad=0.2,
    )
    match_axis_label_fontsize(axis)
    despine(axis)


def plot_ground_truth_evaluation_exact_type(
    network_data: dict,
    output_path: Path,
    snapshot_label: str,
    type_mapping: dict[str, dict[str, str]] | None = None,
) -> dict:
    evaluation = build_exact_type_evaluation(network_data, type_mapping=type_mapping)
    rows = evaluation["approaches"]

    figure, (axis_counts, axis_scores) = plt.subplots(
        2,
        1,
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
        value_formatter=lambda value: f"{value * 100:.0f}%",
        label_offset=0.015,
    )
    axis_scores.set_ylabel("Score")
    axis_scores.set_ylim(0, 1.12)
    axis_scores.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    axis_scores.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
    match_axis_label_fontsize(axis_scores)

    # Keep the suptitle inside the figure bounds (y<1) so the exported PDF
    # does not clip it, and wrap it because the single line is wider than the
    # figure; tight_layout reserves the top band for both lines.
    figure.suptitle(
        "Ground-Truth Evaluation\n"
        f"with Exact Type Matching ({snapshot_label})",
        y=0.99,
        fontsize=FIGURE_TITLE_FONT_SIZE,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.97))
    save_figure(figure, output_path)
    return evaluation
