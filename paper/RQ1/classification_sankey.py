from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import matplotlib
import matplotlib.patheffects as pe
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path

from paper.RQ3._plotting import BAR_EDGE_COLOR, BAR_EDGE_WIDTH, bar_style, save_figure
from paper.RQ1.classification_status import STATUS_COLORS, resolve_rq1_status_order
from paper.RQ1.classification_type import TYPE_COLORS, TYPE_ORDER


LAYER_ORDER = [
    "Applications",
    "Consensus (soft fork)",
    "Peer Services",
    "Unspecified",
    "Consensus (hard fork)",
    "API/RPC",
]

LAYER_COLORS = {
    "Applications": "#4e79a7",
    "Consensus (soft fork)": "#76b7b2",
    "Peer Services": "#59a14f",
    "Unspecified": "#9c9c9c",
    "Consensus (hard fork)": "#e15759",
    "API/RPC": "#f28e2b",
}


@dataclass
class Block:
    name: str
    count: int
    y0: float
    y1: float


def _normalize_layer(value) -> str:
    text = str(value).strip() if value is not None else ""
    if not text or text == "None" or "Unknown" in text:
        return "Unspecified"
    return text


def _normalize_text(value, fallback: str) -> str:
    text = str(value).strip() if value is not None else ""
    if not text or text == "None":
        return fallback
    return text


def _ordered_categories(observed: set[str], preferred_order: list[str]) -> list[str]:
    ordered = [value for value in preferred_order if value in observed]
    ordered.extend(sorted(observed - set(ordered)))
    return ordered


def _stack_blocks(counts: dict[str, int], order: list[str], gap: float) -> dict[str, Block]:
    total = sum(counts.values())
    if total <= 0:
        return {}

    available_height = 1.0 - gap * max(0, len(order) - 1)
    unit = available_height / total
    y = 1.0
    blocks = {}

    for index, name in enumerate(order):
        height = counts[name] * unit
        y1 = y
        y0 = y1 - height
        blocks[name] = Block(name=name, count=counts[name], y0=y0, y1=y1)
        y = y0 - (gap if index < len(order) - 1 else 0)

    return blocks


def _ribbon_patch(
    x0: float,
    x1: float,
    left_y0: float,
    left_y1: float,
    right_y0: float,
    right_y1: float,
    facecolor,
    alpha: float = 0.55,
) -> PathPatch:
    dx = (x1 - x0) * 0.42
    vertices = [
        (x0, left_y1),
        (x0 + dx, left_y1),
        (x1 - dx, right_y1),
        (x1, right_y1),
        (x1, right_y0),
        (x1 - dx, right_y0),
        (x0 + dx, left_y0),
        (x0, left_y0),
        (x0, left_y1),
    ]
    codes = [
        Path.MOVETO,
        Path.CURVE4,
        Path.CURVE4,
        Path.CURVE4,
        Path.LINETO,
        Path.CURVE4,
        Path.CURVE4,
        Path.CURVE4,
        Path.CLOSEPOLY,
    ]
    return PathPatch(
        Path(vertices, codes),
        facecolor=facecolor,
        edgecolor=BAR_EDGE_COLOR,
        linewidth=0.5,
        alpha=alpha,
        joinstyle="round",
        capstyle="round",
    )


def _draw_block(ax, x: float, width: float, block: Block, color: str) -> None:
    style = bar_style(color)
    rect = Rectangle(
        (x, block.y0),
        width,
        block.y1 - block.y0,
        facecolor=style["color"],
        edgecolor=style["edgecolor"],
        linewidth=style["linewidth"],
        zorder=3,
    )
    ax.add_patch(rect)


def _draw_block_label(
    ax,
    x: float,
    width: float,
    block: Block,
    *,
    rotation: float = 0,
    full_label: bool = True,
) -> None:
    height = block.y1 - block.y0
    if full_label:
        text = f"{block.name}\n{block.count}"
    else:
        text = str(block.count)

    fontsize = 9
    if height < 0.14:
        fontsize = 8
    if height < 0.09:
        fontsize = 7
    if height < 0.055:
        text = str(block.count)
        fontsize = 6.5

    ax.text(
        x + width / 2,
        (block.y0 + block.y1) / 2,
        text,
        ha="center",
        va="center",
        rotation=rotation,
        fontsize=fontsize,
        color="#111111",
        zorder=7,
        path_effects=[pe.withStroke(linewidth=2.4, foreground="white", alpha=0.9)],
    )


def _draw_outer_block_name(
    ax,
    x: float,
    block: Block,
    *,
    side: str,
) -> None:
    if side == "left":
        text_x = x - 0.018
        ha = "right"
    else:
        text_x = x + 0.068
        ha = "left"

    display_name = (
        block.name
        .replace("Specification", "Spec-\nification")
        .replace("Informational", "Inform-\national")
        .replace("Consensus (soft fork)", "Consensus\n(soft fork)")
        .replace("Consensus (hard fork)", "Consensus\n(hard fork)")
    )

    ax.text(
        text_x,
        (block.y0 + block.y1) / 2,
        display_name,
        ha=ha,
        va="center",
        fontsize=9.5,
        color="#111111",
        zorder=7,
    )


def _thin_label_adjustment(total: int, index: int, *, side: str) -> tuple[float, float]:
    x_shift = 0.0
    y_shift = 0.0

    if total == 2:
        y_shift = -0.012 if index == 0 else 0.012
    elif total == 3:
        if index == 0:
            y_shift = -0.014
        elif index == 2:
            y_shift = 0.014
        else:
            x_shift = 0.014 if side == "left" else -0.014
    elif total > 3:
        centered_index = index - (total - 1) / 2
        y_shift = centered_index * 0.009

    return x_shift, y_shift


def plot_classification_sankey(
    network_data: dict,
    output_path: Path,
    snapshot_label: str,
    *,
    status_order: list[str] | None = None,
) -> None:
    nodes = network_data.get("nodes", [])
    if not nodes:
        raise ValueError("Classification sankey requires non-empty network nodes.")

    triples = Counter()
    type_counts = Counter()
    status_counts = Counter()
    layer_counts = Counter()

    for node in nodes:
        proposal_type = _normalize_text(node.get("type"), "Unknown Type")
        status = _normalize_text(node.get("status"), "Unknown Status")
        layer = _normalize_layer(node.get("layer"))

        triples[(proposal_type, status, layer)] += 1
        type_counts[proposal_type] += 1
        status_counts[status] += 1
        layer_counts[layer] += 1

    type_order = _ordered_categories(set(type_counts), TYPE_ORDER)
    status_order = _ordered_categories(
        set(status_counts),
        status_order or resolve_rq1_status_order(snapshot_label),
    )
    layer_order = _ordered_categories(set(layer_counts), LAYER_ORDER)

    type_blocks = _stack_blocks(type_counts, type_order, gap=0.03)
    status_blocks = _stack_blocks(status_counts, status_order, gap=0.035)
    layer_blocks = _stack_blocks(layer_counts, layer_order, gap=0.03)

    type_status = Counter()
    status_layer = Counter()
    for proposal_type, status, layer in triples:
        count = triples[(proposal_type, status, layer)]
        type_status[(proposal_type, status)] += count
        status_layer[(status, layer)] += count

    figure, axis = plt.subplots(figsize=(10, 5))
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.axis("off")

    x_type = 0.10
    x_status = 0.445
    x_layer = 0.79
    block_width = 0.05
    left_flow_label_x = x_type + block_width + 0.012
    right_flow_label_x = x_layer - 0.012
    thin_flow_threshold = 8
    left_thin_counts = {
        proposal_type: sum(
            1
            for status in status_order
            if 0 < type_status.get((proposal_type, status), 0) < thin_flow_threshold
        )
        for proposal_type in type_order
    }
    right_thin_counts = {
        layer: sum(
            1
            for status in status_order
            if 0 < status_layer.get((status, layer), 0) < thin_flow_threshold
        )
        for layer in layer_order
    }
    left_thin_indices = {proposal_type: 0 for proposal_type in type_order}
    right_thin_indices = {layer: 0 for layer in layer_order}

    type_outgoing = {name: type_blocks[name].y0 for name in type_order}
    status_incoming = {name: status_blocks[name].y0 for name in status_order}
    for proposal_type in type_order:
        for status in status_order:
            count = type_status.get((proposal_type, status), 0)
            if count <= 0:
                continue
            left_y0 = type_outgoing[proposal_type]
            left_y1 = left_y0 + (type_blocks[proposal_type].y1 - type_blocks[proposal_type].y0) * count / type_blocks[proposal_type].count
            right_y0 = status_incoming[status]
            right_y1 = right_y0 + (status_blocks[status].y1 - status_blocks[status].y0) * count / status_blocks[status].count
            patch = _ribbon_patch(
                x_type + block_width,
                x_status,
                left_y0,
                left_y1,
                right_y0,
                right_y1,
                bar_style(STATUS_COLORS.get(status, "#777777"))["color"],
                alpha=0.5,
            )
            axis.add_patch(patch)
            label_y = (left_y0 + left_y1) / 2
            label_x = left_flow_label_x
            if count < thin_flow_threshold:
                total_thin = left_thin_counts[proposal_type]
                thin_index = left_thin_indices[proposal_type]
                x_shift, y_shift = _thin_label_adjustment(total_thin, thin_index, side="left")
                label_x += x_shift
                label_y += y_shift
                left_thin_indices[proposal_type] += 1
            axis.text(
                label_x,
                label_y,
                str(count),
                ha="left",
                va="center",
                fontsize=6.8,
                color="#111111",
                zorder=6,
                path_effects=[pe.withStroke(linewidth=2.2, foreground="white", alpha=0.95)],
            )
            type_outgoing[proposal_type] = left_y1
            status_incoming[status] = right_y1

    status_outgoing = {name: status_blocks[name].y0 for name in status_order}
    layer_incoming = {name: layer_blocks[name].y0 for name in layer_order}
    for status in status_order:
        for layer in layer_order:
            count = status_layer.get((status, layer), 0)
            if count <= 0:
                continue
            left_y0 = status_outgoing[status]
            left_y1 = left_y0 + (status_blocks[status].y1 - status_blocks[status].y0) * count / status_blocks[status].count
            right_y0 = layer_incoming[layer]
            right_y1 = right_y0 + (layer_blocks[layer].y1 - layer_blocks[layer].y0) * count / layer_blocks[layer].count
            patch = _ribbon_patch(
                x_status + block_width,
                x_layer,
                left_y0,
                left_y1,
                right_y0,
                right_y1,
                bar_style(STATUS_COLORS.get(status, "#777777"))["color"],
                alpha=0.5,
            )
            axis.add_patch(patch)
            label_y = (right_y0 + right_y1) / 2
            label_x = right_flow_label_x
            if count < thin_flow_threshold:
                total_thin = right_thin_counts[layer]
                thin_index = right_thin_indices[layer]
                x_shift, y_shift = _thin_label_adjustment(total_thin, thin_index, side="right")
                label_x += x_shift
                label_y += y_shift
                right_thin_indices[layer] += 1
            axis.text(
                label_x,
                label_y,
                str(count),
                ha="right",
                va="center",
                fontsize=6.8,
                color="#111111",
                zorder=6,
                path_effects=[pe.withStroke(linewidth=2.2, foreground="white", alpha=0.95)],
            )
            status_outgoing[status] = left_y1
            layer_incoming[layer] = right_y1

    for name in type_order:
        _draw_block(axis, x_type, block_width, type_blocks[name], TYPE_COLORS.get(name, "#777777"))
    for name in status_order:
        _draw_block(axis, x_status, block_width, status_blocks[name], STATUS_COLORS.get(name, "#777777"))
    for name in layer_order:
        _draw_block(axis, x_layer, block_width, layer_blocks[name], LAYER_COLORS.get(name, "#777777"))

    for name in type_order:
        block = type_blocks[name]
        _draw_block_label(axis, x_type, block_width, block, rotation=0, full_label=False)
        _draw_outer_block_name(axis, x_type, block, side="left")

    for name in status_order:
        block = status_blocks[name]
        _draw_block_label(axis, x_status, block_width, block, rotation=0, full_label=True)

    for name in layer_order:
        block = layer_blocks[name]
        _draw_block_label(axis, x_layer, block_width, block, rotation=0, full_label=False)
        _draw_outer_block_name(axis, x_layer, block, side="right")

    axis.text(x_type + block_width / 2, 1.015, "Type", ha="center", va="bottom", fontsize=11, fontweight="bold")
    axis.text(x_status + block_width / 2, 1.015, "Status", ha="center", va="bottom", fontsize=11, fontweight="bold")
    axis.text(x_layer + block_width / 2, 1.015, "Layer", ha="center", va="bottom", fontsize=11, fontweight="bold")
    figure.suptitle(f"Classification Sankey ({snapshot_label})", y=0.955)
    figure.tight_layout(rect=(0.01, 0.01, 0.99, 0.965))
    save_figure(figure, output_path)
