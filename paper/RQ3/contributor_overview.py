from pathlib import Path

import numpy as np

import matplotlib.pyplot as plt

from paper.config import FIGURE_TITLE_FONT_SIZE, SUBPLOT_TITLE_FONT_SIZE
from paper.plot_colors import AUTHORSHIP_DISTRIBUTION_COLOR, AUTHORS_PER_BIP_COLOR
from paper.RQ3._plotting import (
    bar_style,
    despine,
    match_axis_label_fontsize,
    save_figure,
)

EVALUATION_FIGSIZE = (5.0, 5.6)
BAR_WIDTH = 0.8


def _log_bin(
    histogram: list[dict[str, int]], x_key: str, y_key: str
) -> tuple[list[str], list[int]]:
    """Group (x, y) frequency points into power-of-two x-ranges, summing y
    within each range, so a long-tailed value range (e.g. 1..189) collapses
    into a handful of bars instead of one per exact value."""
    points = [(int(entry[x_key]), int(entry[y_key])) for entry in histogram]
    max_x = max((x for x, _ in points), default=1)

    edges = [1]
    while edges[-1] <= max_x:
        edges.append(edges[-1] * 2)

    bin_totals = [0] * (len(edges) - 1)
    for x, y in points:
        for i in range(len(edges) - 1):
            if edges[i] <= x < edges[i + 1]:
                bin_totals[i] += y
                break

    labels = []
    for i in range(len(edges) - 1):
        low, high = edges[i], edges[i + 1] - 1
        labels.append(str(low) if low == high else f"{low}-{high}")

    # Drop trailing empty bins past the last populated one (max_x guarantees
    # at least the last bin is non-empty, but earlier gaps can still occur).
    while bin_totals and bin_totals[-1] == 0:
        bin_totals.pop()
        labels.pop()

    return labels, bin_totals


def _draw_binned_histogram_axis(
    axis,
    labels: list[str],
    counts: list[int],
    *,
    title: str | None,
    xlabel: str,
    ylabel: str,
    color: str,
) -> None:
    positions = np.arange(len(labels))
    axis.bar(positions, counts, width=BAR_WIDTH, zorder=2, **bar_style(color))
    if title:
        axis.set_title(title, fontsize=SUBPLOT_TITLE_FONT_SIZE)
    axis.set_xlabel(xlabel)
    axis.set_ylabel(ylabel)
    axis.set_xticks(positions)
    axis.set_xticklabels(labels)
    axis.grid(axis="y", alpha=0.35)
    axis.grid(axis="x", visible=False)
    match_axis_label_fontsize(axis)
    max_count = max(counts) if counts else 1
    for position, count in zip(positions, counts, strict=True):
        axis.text(
            position,
            count + max_count * 0.015,
            str(count),
            ha="center",
            va="bottom",
        )
    despine(axis)


def plot_contributor_overview(
    bip_author_count_histogram: list[dict[str, int]],
    contribution_histogram: list[dict[str, int]],
    output_path: Path,
    snapshot_label: str,
) -> None:
    """Git-contributor counterpart to plot_authorship_overview, binned into
    power-of-two ranges rather than one bar per exact value: contributor
    counts run a much longer tail than declared-author counts (up to ~190 vs.
    ~15), so an unbinned histogram needs far more bars than a single-column
    figure can label without overlap."""
    per_bip_labels, per_bip_counts = _log_bin(
        bip_author_count_histogram, "author_count", "bip_count"
    )
    distribution_labels, distribution_counts = _log_bin(
        contribution_histogram, "bips_written", "authors"
    )

    figure, (axis_top, axis_bottom) = plt.subplots(
        2,
        1,
        figsize=EVALUATION_FIGSIZE,
    )

    _draw_binned_histogram_axis(
        axis_top,
        per_bip_labels,
        per_bip_counts,
        title="(a) Contributors per BIP",
        xlabel="# Contributors",
        ylabel=f"# BIPs ({sum(per_bip_counts)})",
        color=AUTHORS_PER_BIP_COLOR,
    )
    _draw_binned_histogram_axis(
        axis_bottom,
        distribution_labels,
        distribution_counts,
        title="(b) BIPs per Contributor",
        xlabel="# BIPs",
        ylabel=f"# Contributors ({sum(distribution_counts)})",
        color=AUTHORSHIP_DISTRIBUTION_COLOR,
    )

    figure.suptitle(
        f"Contributor Overview ({snapshot_label})",
        y=1.02,
        fontsize=FIGURE_TITLE_FONT_SIZE,
    )
    figure.tight_layout()
    save_figure(figure, output_path)
