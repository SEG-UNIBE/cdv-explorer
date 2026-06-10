from datetime import date
from pathlib import Path

import matplotlib
import matplotlib.patheffects as pe
import numpy as np
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator

from analysis.artifact_io import resolve_latest_snapshot_label
from pipeline.source_context import SourceContext
from paper.plot_colors import with_plot_alpha
from paper.RQ3._plotting import (
    BAR_EDGE_COLOR,
    BAR_EDGE_WIDTH,
    bar_style,
    despine,
    match_axis_label_fontsize,
    save_figure,
)


STATUS_ORDER = [
    "Draft",
    "Deferred",
    "Proposed",
    "Active",
    "Deployed",
    "Complete",
    "Closed",
    "Rejected",
    "Withdrawn",
    "Obsolete",
    "Living",
    "Stagnant",
    "Unknown",
]

STATUS_COLORS = {
    "Draft": "#f08c00",
    "Deferred": "#9c36b5",
    "Proposed": "#1c7ed6",
    "Active": "#0b7285",
    "Final": "#4263eb",
    "Replaced": "#8d6e63",
    "Deployed": "#2f9e44",
    "Complete": "#1971c2",
    "Closed": "#d94841",
    "Rejected": "#868e96",
    "Withdrawn": "#495057",
    "Obsolete": "#5c677d",
    "Living": "#2b8a3e",
    "Stagnant": "#e67700",
    "Unknown": "#adb5bd",
}


def _parse_snapshot_date(snapshot_label: str | None) -> date | None:
    candidate = snapshot_label
    if not candidate or candidate == "latest":
        candidate = resolve_latest_snapshot_label()
    if not candidate:
        return None

    try:
        return date.fromisoformat(str(candidate))
    except ValueError:
        return None


def resolve_rq1_status_order(
    snapshot_label: str | None,
    source_context: SourceContext | None = None,
) -> list[str]:
    snapshot_date = _parse_snapshot_date(snapshot_label)
    context = source_context or SourceContext.default()
    regimes = context.classification_config.get("regimes", [])
    valid_orders: list[list[str]] = []

    for entry in regimes:
        if not isinstance(entry, dict):
            continue

        start_text = entry.get("valid_from")
        end_text = entry.get("valid_until")
        order = entry.get("status_order")
        if not isinstance(order, list) or not order:
            continue
        normalized_order = [str(value) for value in order]
        valid_orders.append(normalized_order)

        start_date = date.fromisoformat(start_text) if start_text else None
        end_date = date.fromisoformat(end_text) if end_text else None

        if snapshot_date is None:
            continue
        if start_date is not None and snapshot_date < start_date:
            continue
        if end_date is not None and snapshot_date > end_date:
            continue

        return normalized_order

    if valid_orders:
        return valid_orders[-1]

    return STATUS_ORDER


def _monotone_cubic_curve(
    x_values: np.ndarray,
    y_values: np.ndarray,
    *,
    points_per_segment: int = 24,
) -> tuple[np.ndarray, np.ndarray]:
    if len(x_values) < 2:
        return x_values, y_values

    h = np.diff(x_values)
    delta = np.diff(y_values) / h
    tangents = np.zeros_like(y_values, dtype=float)

    tangents[0] = delta[0]
    tangents[-1] = delta[-1]

    for index in range(1, len(y_values) - 1):
        left = delta[index - 1]
        right = delta[index]
        if left == 0 or right == 0 or np.sign(left) != np.sign(right):
            tangents[index] = 0
        else:
            tangents[index] = (left + right) / 2

    for index, slope in enumerate(delta):
        if slope == 0:
            tangents[index] = 0
            tangents[index + 1] = 0
            continue

        alpha = tangents[index] / slope
        beta = tangents[index + 1] / slope
        scale = alpha ** 2 + beta ** 2
        if scale > 9:
            tau = 3 / np.sqrt(scale)
            tangents[index] = tau * alpha * slope
            tangents[index + 1] = tau * beta * slope

    smooth_x: list[float] = []
    smooth_y: list[float] = []

    for index in range(len(x_values) - 1):
        x0 = x_values[index]
        x1 = x_values[index + 1]
        y0 = y_values[index]
        y1 = y_values[index + 1]
        segment_width = x1 - x0

        steps = np.linspace(0, 1, points_per_segment, endpoint=False)
        for step in steps:
            h00 = (2 * step ** 3) - (3 * step ** 2) + 1
            h10 = step ** 3 - (2 * step ** 2) + step
            h01 = (-2 * step ** 3) + (3 * step ** 2)
            h11 = step ** 3 - step ** 2

            smooth_x.append(x0 + step * segment_width)
            smooth_y.append(
                (h00 * y0)
                + (h10 * segment_width * tangents[index])
                + (h01 * y1)
                + (h11 * segment_width * tangents[index + 1])
            )

    smooth_x.append(x_values[-1])
    smooth_y.append(y_values[-1])
    return np.array(smooth_x), np.array(smooth_y)


def _normalize_status_series(
    status_over_time: dict[str, dict[str, int]],
    order: list[str],
) -> tuple[list[int], list[str], dict[str, list[int]]]:
    if not status_over_time:
        raise ValueError("Classification plot requires non-empty over-time data.")

    years = sorted(int(year) for year in status_over_time.keys())
    observed_statuses = {
        str(status)
        for yearly_statuses in status_over_time.values()
        for status, count in yearly_statuses.items()
        if int(count) > 0
    }
    ordered_statuses = [
        status
        for status in order
        if status in observed_statuses
    ]
    ordered_statuses.extend(sorted(observed_statuses - set(ordered_statuses)))

    series = {
        status: [
            int(status_over_time.get(str(year), {}).get(status, 0))
            for year in years
        ]
        for status in ordered_statuses
    }
    return years, ordered_statuses, series


def plot_classification_status(
    status_over_time: dict[str, dict[str, int]],
    output_path: Path,
    snapshot_label: str,
    *,
    category_title: str = "Classification Status",
    center_label: str = "BIPs",
    order: list[str] | None = None,
    colors: dict[str, str] | None = None,
    left_axis_title: str = "Status",
    right_axis_title: str = "Number of BIPs",
    right_secondary_axis_title: str = "Cumulative number of BIPs",
) -> None:
    years, ordered_statuses, series = _normalize_status_series(
        status_over_time,
        order or resolve_rq1_status_order(snapshot_label),
    )
    totals = {
        status: sum(counts)
        for status, counts in series.items()
    }
    total_bips = sum(totals.values())
    if total_bips <= 0:
        raise ValueError("Classification plot requires positive category counts.")

    palette = colors or STATUS_COLORS
    colors = [palette.get(status, "#868e96") for status in ordered_statuses]
    legend_handles = [
        Patch(facecolor=with_plot_alpha(color), edgecolor="none", label=status)
        for status, color in zip(ordered_statuses, colors)
    ]
    donut_colors = [bar_style(color)["color"] for color in colors]
    x_positions = np.arange(len(years))

    figure, (axis_left, axis_right) = plt.subplots(
        1,
        2,
        figsize=(10, 3.5),
        gridspec_kw={"width_ratios": [0.33, 0.67]},
    )
    axis_right_secondary = axis_right.twinx()

    donut_values = [totals[status] for status in ordered_statuses]

    def _autopct(percent: float) -> str:
        return f"{percent:.0f}%"

    wedges, _, autotexts = axis_left.pie(
        donut_values,
        colors=donut_colors,
        startangle=90,
        counterclock=False,
        radius=1.18,
        wedgeprops={
            "width": 0.5,
            "linewidth": BAR_EDGE_WIDTH,
        },
        autopct=_autopct,
        pctdistance=1.2,
        textprops={"fontsize": 9, "color": "#343a40"},
    )
    for wedge in wedges:
        wedge.set_edgecolor(BAR_EDGE_COLOR)
    for autotext in autotexts:
        autotext.set_fontsize(9)
        autotext.set_color("#343a40")

    axis_left.text(
        0,
        0,
        f"{total_bips}\n{center_label}",
        ha="center",
        va="center",
        fontsize=12,
        fontweight="bold",
        color="#343a40",
    )
    axis_left.set_aspect("equal")
    axis_left.set_xlim(-1.35, 1.35)
    axis_left.set_ylim(-1.28, 1.28)

    bar_bottom = np.zeros(len(years), dtype=int)
    for status, color in zip(ordered_statuses, colors):
        counts = series[status]
        axis_right.bar(
            x_positions,
            counts,
            bottom=bar_bottom,
            width=0.8,
            zorder=2,
            **bar_style(color),
        )
        bar_bottom = bar_bottom + np.array(counts)

    axis_right.set_xlabel("Year")
    axis_right.set_ylabel(right_axis_title)
    axis_right.set_xticks(x_positions)
    axis_right.set_xticklabels(years, rotation=45, ha="right")
    axis_right.set_xlim(-0.6, len(years) - 0.4)
    axis_right.yaxis.set_major_locator(MaxNLocator(integer=True))
    axis_right.grid(axis="y", alpha=0.35)
    axis_right.grid(axis="x", visible=False)
    match_axis_label_fontsize(axis_right)
    despine(axis_right)

    cumulative_max = 0
    for status, color in zip(ordered_statuses, colors):
        cumulative_counts = np.cumsum(series[status]).astype(float)
        cumulative_max = max(cumulative_max, int(cumulative_counts[-1]) if len(cumulative_counts) else 0)
        smooth_x, smooth_y = _monotone_cubic_curve(
            x_positions.astype(float),
            cumulative_counts,
        )
        line, = axis_right_secondary.plot(
            smooth_x,
            smooth_y,
            color=with_plot_alpha(color),
            linewidth=1,
            zorder=4,
        )
        line.set_path_effects([
            pe.Stroke(linewidth=2, foreground="white", alpha=0.9),
            pe.Normal(),
        ])
        axis_right_secondary.scatter(
            x_positions,
            cumulative_counts,
            color=with_plot_alpha(color),
            s=18,
            zorder=5,
            edgecolors="white",
            linewidths=0.6,
        )

    axis_right_secondary.set_ylabel(right_secondary_axis_title)
    axis_right_secondary.set_xlim(-0.6, len(years) - 0.4)
    axis_right_secondary.set_ylim(0, cumulative_max * 1.05 if cumulative_max > 0 else 1)
    axis_right_secondary.yaxis.set_major_locator(MaxNLocator(integer=True))
    axis_right_secondary.grid(False)
    match_axis_label_fontsize(axis_right_secondary)
    axis_right_secondary.spines["top"].set_visible(False)
    axis_right_secondary.spines["left"].set_visible(False)

    figure.suptitle(f"{category_title} ({snapshot_label})", y=0.98)
    figure.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.93),
        ncol=4,
        frameon=False,
        columnspacing=1.4,
        handlelength=1.2,
    )
    figure.tight_layout(rect=(0, 0, 0.95, 0.92))
    save_figure(figure, output_path)
