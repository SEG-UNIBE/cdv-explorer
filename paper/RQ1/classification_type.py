from pathlib import Path

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator

from analysis.classification.metrics import build_type_over_time
from paper.plot_colors import BIP_TYPE_COLORS, BIP_TYPE_ORDER, with_plot_alpha
from paper.RQ1.classification_status import (
    _monotone_cubic_curve,
    _normalize_status_series,
    plot_classification_status,
)
from paper.RQ3._plotting import bar_style, despine, match_axis_label_fontsize, save_figure


TYPE_ORDER = BIP_TYPE_ORDER
TYPE_COLORS = BIP_TYPE_COLORS

STACKED_TYPE_FIGSIZE = (9.8, 2.6)
STACKED_TYPE_WIDTH_RATIOS = (0.63, 0.21)
STACKED_TYPE_WSPACE = 0.16
STACKED_TYPE_BAR_WIDTH = 0.8
STACKED_TYPE_SHARE_LABEL_X_PADDING = 0.5
STACKED_TYPE_RIGHT_MARGIN = 1.45
STACKED_TYPE_SHARE_LABEL_MIN_GAP_FRACTION = 0.1


def plot_classification_type(
    network_data: dict,
    output_path: Path,
    snapshot_label: str,
) -> None:
    nodes = network_data.get("nodes", [])
    type_over_time = build_type_over_time(nodes)
    plot_classification_status(
        status_over_time=type_over_time,
        output_path=output_path,
        snapshot_label=snapshot_label,
        category_title="Classification Type",
        center_label="BIPs",
        order=TYPE_ORDER,
        colors=TYPE_COLORS,
        left_axis_title="Type",
        right_axis_title="#BIPs",
        right_secondary_axis_title="Cumulative #BIPs",
    )


def plot_classification_type_stacked(
    network_data: dict,
    output_path: Path,
    snapshot_label: str,
) -> None:
    nodes = network_data.get("nodes", [])
    type_over_time = build_type_over_time(nodes)
    years, ordered_types, series = _normalize_status_series(type_over_time, TYPE_ORDER)

    totals = {
        kind: sum(counts)
        for kind, counts in series.items()
    }
    total_bips = sum(totals.values())
    if total_bips <= 0:
        raise ValueError("Classification type stacked plot requires positive type counts.")

    colors = [TYPE_COLORS.get(kind, "#868e96") for kind in ordered_types]
    legend_handles = [
        Patch(
            facecolor=bar_style(color)["color"],
            edgecolor="#000000",
            linewidth=0.7,
            label=f"{kind} ({totals[kind]})",
        )
        for kind, color in zip(ordered_types, colors)
    ]
    x_positions = np.arange(len(years), dtype=float)

    figure, (axis_right, legend_axis) = plt.subplots(
        1,
        2,
        figsize=STACKED_TYPE_FIGSIZE,
        gridspec_kw={
            "width_ratios": list(STACKED_TYPE_WIDTH_RATIOS),
            "wspace": STACKED_TYPE_WSPACE,
        },
    )
    legend_axis.axis("off")
    axis_right_secondary = axis_right.twinx()

    legend = legend_axis.legend(
        handles=legend_handles,
        loc="center right",
        bbox_to_anchor=(0.98, 0.5),
        frameon=False,
        ncol=1,
        title="BIP Type:",
        handlelength=2.0,
        labelspacing=0.8,
        borderaxespad=0,
    )
    legend._legend_box.align = "left"

    bar_bottom = np.zeros(len(years), dtype=int)
    for kind, color in zip(ordered_types, colors):
        counts = series[kind]
        axis_right.bar(
            x_positions,
            counts,
            bottom=bar_bottom,
            width=STACKED_TYPE_BAR_WIDTH,
            zorder=2,
            **bar_style(color),
        )
        bar_bottom = bar_bottom + np.array(counts)

    # axis_right.set_xlabel("Year")
    axis_right.set_ylabel("#BIPs")
    axis_right.set_xticks(x_positions)
    axis_right.set_xticklabels(
        [year if i % 2 == 0 else "" for i, year in enumerate(years)],
        rotation=0,
        ha="center",
        fontsize=9,
    )
    axis_right.set_xlim(
        -0.6,
        float(x_positions[-1]) + STACKED_TYPE_RIGHT_MARGIN,
    )
    axis_right.yaxis.set_major_locator(MaxNLocator(integer=True))
    axis_right.grid(axis="y", alpha=0.35)
    axis_right.grid(axis="x", visible=False)
    match_axis_label_fontsize(axis_right)
    despine(axis_right, right=False)

    cumulative_max = 0.0
    final_points = []
    for kind, color in zip(ordered_types, colors):
        cumulative_counts = np.cumsum(series[kind]).astype(float)
        cumulative_max = max(cumulative_max, float(cumulative_counts[-1]) if len(cumulative_counts) else 0.0)
        smooth_x, smooth_y = _monotone_cubic_curve(
            x_positions,
            cumulative_counts,
        )
        line, = axis_right_secondary.plot(
            smooth_x,
            smooth_y,
            color=with_plot_alpha(color),
            linewidth=1.2,
            zorder=4,
        )
        line.set_path_effects([
            pe.Stroke(linewidth=2.2, foreground="white", alpha=0.9),
            pe.Normal(),
        ])
        axis_right_secondary.scatter(
            x_positions,
            cumulative_counts,
            color=with_plot_alpha(color),
            s=28,
            zorder=5,
            edgecolors="white",
            linewidths=0.7,
        )
        final_points.append(
            {
                "kind": kind,
                "color": color,
                "y": float(cumulative_counts[-1]),
                "share": float(totals[kind] / total_bips),
            }
        )

    label_gap = max(2.0, cumulative_max * STACKED_TYPE_SHARE_LABEL_MIN_GAP_FRACTION)
    adjusted_y_by_kind = {}
    current_y = None
    for point in sorted(final_points, key=lambda item: item["y"]):
        adjusted_y = point["y"]
        if current_y is not None and adjusted_y < current_y + label_gap:
            adjusted_y = current_y + label_gap
        adjusted_y_by_kind[point["kind"]] = adjusted_y
        current_y = adjusted_y

    label_top = max(adjusted_y_by_kind.values(), default=0.0)
    axis_right_secondary.set_ylabel("Cumulative #BIPs")
    axis_right_secondary.set_xlim(
        -0.6,
        float(x_positions[-1]) + STACKED_TYPE_RIGHT_MARGIN,
    )
    axis_right_secondary.set_ylim(0, max(1.0, cumulative_max * 1.05, label_top + label_gap * 0.6))
    axis_right_secondary.yaxis.set_major_locator(MaxNLocator(integer=True))
    axis_right_secondary.grid(False)
    match_axis_label_fontsize(axis_right_secondary)
    axis_right_secondary.spines["top"].set_visible(False)
    axis_right_secondary.spines["left"].set_visible(False)

    label_x = float(x_positions[-1]) + STACKED_TYPE_SHARE_LABEL_X_PADDING
    for point in final_points:
        adjusted_y = adjusted_y_by_kind[point["kind"]]
        if abs(adjusted_y - point["y"]) > 0.15:
            axis_right_secondary.plot(
                [float(x_positions[-1]), label_x - 0.5],
                [point["y"], adjusted_y],
                color=with_plot_alpha(point["color"], 0.7),
                linewidth=0.8,
                zorder=5,
            )
        share_label = f"{point['share'] * 100:.0f}%"
        text = axis_right_secondary.text(
            label_x,
            adjusted_y,
            share_label,
            color=with_plot_alpha(point["color"]),
            fontsize=10,
            fontweight="bold",
            ha="left",
            va="center",
            zorder=6,
            clip_on=False,
        )
        text.set_path_effects([
            pe.Stroke(linewidth=3.0, foreground="white", alpha=0.95),
            pe.Normal(),
        ])

    figure.suptitle(f"Classification Type ({snapshot_label})", y=0.98)
    figure.subplots_adjust(left=0.07, right=0.98, bottom=0.14, top=0.88, wspace=STACKED_TYPE_WSPACE)
    save_figure(figure, output_path)
