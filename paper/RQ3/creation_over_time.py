from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from paper.plot_colors import with_plot_alpha
from paper.RQ3._plotting import bar_style, despine, match_axis_label_fontsize, save_figure


TIMELINE_BAR_COLOR = "#4c78a8"
TIMELINE_LINE_COLOR = "#e45756"


def plot_creation_over_time(
    proposals_per_year: list[dict[str, int]],
    output_path: Path,
    snapshot_label: str,
) -> None:
    if not proposals_per_year:
        raise ValueError("Creation-over-time plot requires non-empty proposals_per_year data.")

    years = [int(entry["year"]) for entry in proposals_per_year]
    yearly_counts = [int(entry["count"]) for entry in proposals_per_year]
    cumulative_counts = np.cumsum(yearly_counts)
    x_positions = np.arange(len(years))

    figure, axis_left = plt.subplots(figsize=(10, 4))
    axis_right = axis_left.twinx()

    axis_left.bar(
        x_positions,
        yearly_counts,
        width=0.72,
        zorder=2,
        **bar_style(TIMELINE_BAR_COLOR),
    )
    axis_right.plot(
        x_positions,
        cumulative_counts,
        color=with_plot_alpha(TIMELINE_LINE_COLOR),
        linewidth=2.2,
        marker="o",
        zorder=3,
    )

    axis_left.set_xticks(x_positions)
    axis_left.set_xticklabels(years, rotation=45, ha="right")
    axis_left.set_ylabel("New proposals")
    axis_right.set_ylabel("Cumulative total")
    axis_left.set_xlabel("Year")
    axis_left.set_title(f"Creation Over Time ({snapshot_label})")
    axis_left.set_xlim(-0.6, len(years) - 0.4)
    axis_left.set_ylim(0, max(yearly_counts) * 1.16)
    axis_left.grid(axis="y", alpha=0.35)
    axis_right.grid(False)
    match_axis_label_fontsize(axis_left)
    match_axis_label_fontsize(axis_right)
    despine(axis_left)
    axis_right.spines["top"].set_visible(False)
    axis_right.spines["left"].set_visible(False)

    label_offset = max(yearly_counts) * 0.025
    for x_position, count in zip(x_positions, yearly_counts):
        axis_left.text(
            x_position,
            count + label_offset,
            str(count),
            ha="center",
            va="bottom",
            fontsize=9,
            color="#111111",
        )

    figure.tight_layout()
    save_figure(figure, output_path)
