from pathlib import Path

import matplotlib.pyplot as plt

from paper.plot_colors import PLOT_COLOR_ALPHA, with_plot_alpha


BAR_FILL_ALPHA = PLOT_COLOR_ALPHA
BAR_EDGE_WIDTH = 1.0
BAR_EDGE_COLOR = "#000000"
ELLIPSIS_TICK_COLOR = "#666666"
ELLIPSIS_TICK_WEIGHT = "bold"


def despine(axis, *, right: bool = True) -> None:
    axis.spines["top"].set_visible(False)
    if right:
        axis.spines["right"].set_visible(False)


def bar_style(color: str, *, edgecolor: str | None = None) -> dict[str, object]:
    return {
        "color": with_plot_alpha(color, BAR_FILL_ALPHA),
        "edgecolor": edgecolor or BAR_EDGE_COLOR,
        "linewidth": BAR_EDGE_WIDTH,
    }


def match_axis_label_fontsize(axis) -> None:
    ticklabels = [
        *axis.get_xticklabels(),
        *axis.get_yticklabels(),
    ]

    tick_fontsize = None
    for ticklabel in ticklabels:
        size = ticklabel.get_fontsize()
        if size:
            tick_fontsize = float(size)
            break

    if tick_fontsize is None:
        tick_fontsize = float(plt.rcParams.get("font.size", 10))

    axis.xaxis.label.set_size(tick_fontsize)
    axis.yaxis.label.set_size(tick_fontsize)


def style_ellipsis_ticklabels(axis, tick_labels: list[str], *, ellipsis_label: str = "...") -> None:
    xticklabels = axis.get_xticklabels()
    for tick_index, label in enumerate(tick_labels):
        if label != ellipsis_label:
            continue
        if tick_index >= len(xticklabels):
            continue
        xticklabels[tick_index].set_color(ELLIPSIS_TICK_COLOR)
        xticklabels[tick_index].set_fontweight(ELLIPSIS_TICK_WEIGHT)


def add_bar_label_headroom(axis, *, ratio: float = 0.08, min_extra: float = 0.6) -> None:
    bar_heights = [patch.get_height() for patch in axis.patches]
    if not bar_heights:
        return
    ymax = max(bar_heights)
    extra = max(ymax * ratio, min_extra)
    lower, upper = axis.get_ylim()
    axis.set_ylim(lower, max(upper, ymax + extra))


def save_figure(figure, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, format="pdf")
    plt.close(figure)
