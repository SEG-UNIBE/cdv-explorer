from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator

from paper.config import FIGURE_TITLE_FONT_SIZE, LEGEND_FONT_SIZE, SUBPLOT_TITLE_FONT_SIZE
from paper.plot_colors import ORDERED_PLOT_PALETTE
from paper.RQ3._plotting import despine, match_axis_label_fontsize, save_figure

ORIGINATOR_COLOR = ORDERED_PLOT_PALETTE[0]  # blue
CONTRIBUTOR_COLOR = ORDERED_PLOT_PALETTE[1]  # red

# Covers both panels' ranges (up to ~56 and ~189); ticks past an axis's own
# data max simply fall outside its xlim and aren't drawn.
POWER_OF_TWO_TICKS = (1, 2, 4, 8, 16, 32, 64, 128, 256)

EVALUATION_FIGSIZE = (5.0, 5)
LINE_WIDTH = 1.4


def _weighted_ecdf(
    histogram: list[dict[str, int]], x_key: str, weight_key: str
) -> tuple[list[int], list[float], int]:
    """Empirical CDF over a frequency histogram: `weight_key` counts how many
    entities share each `x_key` value, so the CDF step height at x is the
    running weight share rather than a per-entity 1/n step."""
    points = sorted(
        ((int(entry[x_key]), int(entry[weight_key])) for entry in histogram),
        key=lambda point: point[0],
    )
    total = sum(weight for _, weight in points)
    xs: list[int] = []
    ys: list[float] = []
    cumulative = 0
    for x, weight in points:
        cumulative += weight
        xs.append(x)
        ys.append(cumulative / total if total else 0.0)
    return xs, ys, total


def _draw_ecdf_axis(
    axis,
    series: list[tuple[str, tuple[list[int], list[float], int], str]],
    *,
    title: str | None,
    xlabel: str,
) -> None:
    for label, (xs, ys, total), color in series:
        axis.step(
            xs,
            ys,
            where="post",
            label=f"{label} ({total})",
            color=color,
            linewidth=LINE_WIDTH,
            zorder=2,
        )
    if title:
        axis.set_title(title, fontsize=SUBPLOT_TITLE_FONT_SIZE)
    min_x = min(xs[0] for _, (xs, _, _), _ in series)
    axis.set_xscale("log", base=2)
    axis.xaxis.set_major_locator(FixedLocator(POWER_OF_TWO_TICKS))
    axis.xaxis.set_minor_locator(NullLocator())
    axis.xaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"{value:.0f}"))
    axis.set_xlim(left=min_x)
    axis.set_xlabel(xlabel)
    axis.set_ylabel("Cumulative Share")
    axis.set_ylim(0, 1.02)
    axis.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    axis.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
    axis.tick_params(which="major", length=5)
    axis.grid(True, which="major", alpha=0.35)
    axis.legend(frameon=False, fontsize=LEGEND_FONT_SIZE, loc="lower right")
    match_axis_label_fontsize(axis)
    despine(axis)


def plot_originator_contributor_ecdf(
    originator_bip_count_histogram: list[dict[str, int]],
    contributor_bip_count_histogram: list[dict[str, int]],
    originator_contribution_histogram: list[dict[str, int]],
    contributor_contribution_histogram: list[dict[str, int]],
    output_path: Path,
    snapshot_label: str,
) -> None:
    """Overlay declared-originator and git-contributor distributions on a
    shared cumulative-share axis, for the two histograms already
    plotted separately per source in authorship_overview.py /
    contributor_overview.py: this makes the two directly comparable without
    the KDE-smoothing artifacts a violin plot would introduce on data this
    discrete and tie-heavy, or the visual noise a swarm plot would add at
    455 points."""
    figure, (axis_top, axis_bottom) = plt.subplots(
        2,
        1,
        figsize=EVALUATION_FIGSIZE,
    )

    _draw_ecdf_axis(
        axis_top,
        [
            (
                "Originators",
                _weighted_ecdf(
                    originator_bip_count_histogram, "author_count", "bip_count"
                ),
                ORIGINATOR_COLOR,
            ),
            (
                "Contributors",
                _weighted_ecdf(
                    contributor_bip_count_histogram, "author_count", "bip_count"
                ),
                CONTRIBUTOR_COLOR,
            ),
        ],
        title="(a) People per BIP",
        xlabel="# People",
    )
    _draw_ecdf_axis(
        axis_bottom,
        [
            (
                "Originators",
                _weighted_ecdf(
                    originator_contribution_histogram, "bips_written", "authors"
                ),
                ORIGINATOR_COLOR,
            ),
            (
                "Contributors",
                _weighted_ecdf(
                    contributor_contribution_histogram, "bips_written", "authors"
                ),
                CONTRIBUTOR_COLOR,
            ),
        ],
        title="(b) BIPs per Person",
        xlabel="# BIPs",
    )

    figure.suptitle(
        f"Originators vs. Contributors ({snapshot_label})",
        y=1.02,
        fontsize=FIGURE_TITLE_FONT_SIZE,
    )
    figure.tight_layout()
    save_figure(figure, output_path)
