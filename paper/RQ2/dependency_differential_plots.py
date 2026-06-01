import argparse
import json
import math
import re
import sys
from collections.abc import Sequence as SequenceABC
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
# matplotlib.rcParams["mathtext.fontset"] = "cm"
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.lines import Line2D

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis.artifact_io import load_network_data, resolve_latest_snapshot_label
from analysis.dependencies.constants import (
    BODY_EXTRACTED_LLM,
    BODY_EXTRACTED_REGEX,
    DEPENDENCY_APPROACH_SHORT_LABELS,
    PREAMBLE_EXTRACTED,
)
from paper.RQ2.dependency_plots import (
    ARROW_LEGEND_HANDLER_MAP,
    build_arrow_legend_handle,
    compute_layout_positions,
    get_links_by_type,
    resolve_near_overlaps,
)
from paper._utils.io import resolve_output_dir, snapshot_prefix
from paper.config import SNAPSHOT
from paper.plot_colors import BIP_TYPE_COLORS, BIP_TYPE_ORDER, NEUTRAL_PLOT_COLOR, PLOT_COLOR_ALPHA, with_plot_alpha

DEFAULT_FOCUS_BIPS = [1, 2, 3]
DEFAULT_EXCLUDE_BIPS: list[int] = []
DEFAULT_LAYOUT_NAME = "kamada_kawai"
DEFAULT_OUTPUT_DIR = Path("paper") / "RQ2" / "outputs"
DIFF_LAYOUT_COMPACTION = 0.6
DIFF_LAYOUT_COMPACTION_BY_LAYOUT = {
    "spectral": 0.92,
    "circular": 0.9,
    "shell": 0.88,
    "bipartite": 0.95,
    "multipartite": 0.98,
}
DIFF_LAYOUT_OVERLAP_THRESHOLD = 0.085
DIFF_NODE_SIZE_MIN = 320
DIFF_NODE_SIZE_MAX = 880
DIFF_EDGE_WIDTH = 1.5
DIFF_ARROWHEAD_OVERLAY_WIDTH = 0.0
DIFF_ARROW_SIZE = 14
NODE_FILL_ALPHA = PLOT_COLOR_ALPHA
NODE_LABEL_FONT_SIZE = 7
DIFF_LABEL_OFFSET = 0.035
EDGE_CURVATURE = 0.2
RECIPROCAL_EDGE_CURVATURE = 0.2
EDGE_CURVATURE_OVERRIDES = {
    # Nudge this reciprocal edge a bit further left than the shared default.
    ("350", "173"): 0.1,
    ("350", "141"): 0.1,
    ("67", "13"): -0.1,
}
APPROACH_ONLY_EDGE_COLOR = "#9A9A9AF8"
APPROACH_ONLY_EDGE_STYLE = "dotted"
OVERLAP_EDGE_COLOR = "#16A34A"
BASELINE_ONLY_EDGE_COLOR = "#FF0000"
BASELINE_ONLY_EDGE_STYLE = "dashed"
LAYOUT_EDGE_TYPES = (PREAMBLE_EXTRACTED, BODY_EXTRACTED_REGEX, BODY_EXTRACTED_LLM)
TYPE_ORDER = BIP_TYPE_ORDER
TYPE_COLORS = BIP_TYPE_COLORS
FALLBACK_TYPE_COLOR = NEUTRAL_PLOT_COLOR
COMPARISON_PLOTS = (
    {
        "filename_stem": "preamlbe_vs_regex",
        "approach": BODY_EXTRACTED_REGEX,
        "baseline": PREAMBLE_EXTRACTED,
        "title": "Selected proposals with differential dependencies (Preamble vs. Regex)",
        "subplot_title": "Preamble vs. Regex",
    },
    {
        "filename_stem": "regex_vs_llm",
        "approach": BODY_EXTRACTED_LLM,
        "baseline": BODY_EXTRACTED_REGEX,
        "title": "Selected proposals with differential dependencies (Regex vs. LLM)",
        "subplot_title": "Regex vs. LLM",
    },
)
COMBINED_REACT_DIFFDEP_FILENAME_STEM = "combined"
SINGLE_COMPARISON_FIGSIZE = (3, 5)
COMBINED_COMPARISON_FIGSIZE = (8, 4.5)
DEFAULT_AXIS_MARGIN_SCALE = 0.18
COMBINED_AXIS_MARGIN_SCALE = 0.1
COMBINED_SUBPLOT_TITLE_FONT_SIZE = 9.0
COMBINED_SUBPLOT_TITLE_PAD = 9
COMBINED_EDGE_LEGEND_FONT_SIZE = 7
COMBINED_EDGE_LEGEND_TITLE_FONT_SIZE = 7
COMBINED_NODE_LEGEND_FONT_SIZE = 7
COMBINED_NODE_LEGEND_TITLE_FONT_SIZE = 7


def _build_edge_styles(*, comparison_ordered: bool = False) -> dict[str, dict[str, Any]]:
    return {
        "approach_only": {"color": with_plot_alpha(APPROACH_ONLY_EDGE_COLOR), "style": APPROACH_ONLY_EDGE_STYLE, "alpha": 1.0},
        "overlap": {"color": with_plot_alpha(OVERLAP_EDGE_COLOR), "style": "solid", "alpha": 1.0},
        "baseline_only": {"color": with_plot_alpha(BASELINE_ONLY_EDGE_COLOR), "style": BASELINE_ONLY_EDGE_STYLE, "alpha": 1.0},
    }


def _build_edge_key(source: Any, target: Any) -> tuple[str, str]:
    return str(source), str(target)


def _normalize_focus_ids(bips: Iterable[int | str] | None) -> set[str]:
    normalized = set()
    if bips is None:
        return normalized

    for value in bips:
        match = re.search(r"(\d+)", str(value))
        if match:
            normalized.add(str(int(match.group(1))))
    return normalized


def _type_color(value: Any) -> str:
    return TYPE_COLORS.get(str(value).strip(), FALLBACK_TYPE_COLOR)


def _edge_in_focus_neighborhood(source_id: str, target_id: str, focus_ids: set[str]) -> bool:
    if not focus_ids:
        return True
    return source_id in focus_ids or target_id in focus_ids


def _collect_display_node_ids(
    network_data: Dict[str, Any],
    focus_bips: Sequence[int | str] | None,
    exclude_bips: Sequence[int | str] | None = None,
) -> tuple[set[str], set[str]]:
    excluded_ids = _normalize_focus_ids(exclude_bips)
    node_ids = {
        str(node.get("id"))
        for node in network_data.get("nodes", [])
        if node.get("id") is not None and str(node.get("id")) not in excluded_ids
    }
    focus_ids = _normalize_focus_ids(focus_bips)
    focus_ids -= excluded_ids
    if not focus_ids:
        return node_ids, focus_ids

    display_ids = {node_id for node_id in node_ids if node_id in focus_ids}
    for link_type in LAYOUT_EDGE_TYPES:
        for edge in get_links_by_type(network_data.get("links", {}), link_type):
            source_id = str(edge.get("source"))
            target_id = str(edge.get("target"))
            if _edge_in_focus_neighborhood(source_id, target_id, focus_ids):
                if source_id in node_ids:
                    display_ids.add(source_id)
                if target_id in node_ids:
                    display_ids.add(target_id)
    return display_ids, focus_ids


def _assign_multipartite_subsets(graph: nx.DiGraph, focus_ids: set[str]) -> None:
    if not focus_ids:
        for node_id in graph.nodes():
            graph.nodes[node_id]["subset"] = 0
        return

    ordered_focus_ids = sorted((node_id for node_id in graph.nodes() if node_id in focus_ids), key=int)
    focus_rank = {node_id: index for index, node_id in enumerate(ordered_focus_ids)}

    for focus_id, rank in focus_rank.items():
        graph.nodes[focus_id]["subset"] = 2 * rank
        graph.nodes[focus_id]["anchor_focus"] = focus_id

    for node_id in graph.nodes():
        if node_id in focus_rank:
            continue

        scored_focuses = []
        for focus_id in ordered_focus_ids:
            relation_score = int(graph.has_edge(node_id, focus_id)) + int(graph.has_edge(focus_id, node_id))
            if relation_score <= 0:
                continue
            scored_focuses.append((relation_score, -focus_rank[focus_id], focus_id))

        if scored_focuses:
            scored_focuses.sort(reverse=True)
            anchor_focus = scored_focuses[0][2]
        else:
            anchor_focus = ordered_focus_ids[0]

        graph.nodes[node_id]["anchor_focus"] = anchor_focus
        graph.nodes[node_id]["subset"] = 2 * focus_rank[anchor_focus] + 1


def _build_layout_graph(network_data: Dict[str, Any], display_ids: set[str], focus_ids: set[str]) -> nx.DiGraph:
    graph = nx.DiGraph()

    for node in network_data.get("nodes", []):
        node_id = str(node.get("id"))
        if node_id not in display_ids:
            continue
        proposal_type = str(node.get("type")).strip() or "Unknown Type"
        graph.add_node(node_id, group=proposal_type)

    seen_edges = set()
    for link_type in LAYOUT_EDGE_TYPES:
        for edge in get_links_by_type(network_data.get("links", {}), link_type):
            source_id = str(edge.get("source"))
            target_id = str(edge.get("target"))
            key = _build_edge_key(source_id, target_id)
            if (
                source_id not in display_ids
                or target_id not in display_ids
                or not _edge_in_focus_neighborhood(source_id, target_id, focus_ids)
                or key in seen_edges
            ):
                continue
            graph.add_edge(source_id, target_id)
            seen_edges.add(key)

    _assign_multipartite_subsets(graph, focus_ids)
    return graph


def _compute_base_positions(graph: nx.DiGraph, layout_name: str = DEFAULT_LAYOUT_NAME) -> dict[str, Any]:
    if graph.number_of_nodes() == 0:
        return {}
    try:
        return compute_layout_positions(graph, layout_name)
    except (ImportError, ModuleNotFoundError):
        if layout_name == "kamada_kawai":
            return compute_layout_positions(graph, "spring_default")
        raise


def _compact_positions(pos: dict[str, Any], compaction: float) -> dict[str, Any]:
    if len(pos) <= 1:
        return pos

    x_center = sum(coords[0] for coords in pos.values()) / len(pos)
    y_center = sum(coords[1] for coords in pos.values()) / len(pos)
    compacted = {
        node_id: (
            x_center + (coords[0] - x_center) * compaction,
            y_center + (coords[1] - y_center) * compaction,
        )
        for node_id, coords in pos.items()
    }
    resolve_near_overlaps(compacted, threshold=DIFF_LAYOUT_OVERLAP_THRESHOLD, max_iterations=20)
    return compacted


def _get_layout_compaction(layout_name: str) -> float:
    return DIFF_LAYOUT_COMPACTION_BY_LAYOUT.get(layout_name, DIFF_LAYOUT_COMPACTION)


def _load_exported_positions(layout_export_path: Path, required_node_ids: Iterable[str]) -> dict[str, tuple[float, float]]:
    payload = json.loads(layout_export_path.read_text(encoding="utf8"))
    raw_positions = payload.get("positions")
    normalized_positions: dict[str, tuple[float, float]] = {}

    if isinstance(raw_positions, dict):
        for node_id, coords in raw_positions.items():
            if isinstance(coords, SequenceABC) and len(coords) >= 2:
                normalized_positions[str(node_id)] = (float(coords[0]), float(coords[1]))

    if not normalized_positions:
        for node in payload.get("nodes", []):
            node_id = node.get("id")
            x_coord = node.get("x")
            y_coord = node.get("y")
            if node_id is None or x_coord is None or y_coord is None:
                continue
            normalized_positions[str(node_id)] = (float(x_coord), float(y_coord))

    required_ids = {str(node_id) for node_id in required_node_ids}
    return {node_id: normalized_positions[node_id] for node_id in required_ids if node_id in normalized_positions}


def _project_fallback_positions_into_export_space(
    fallback_pos: dict[str, tuple[float, float]],
    export_pos: dict[str, tuple[float, float]],
    node_ids: Iterable[str],
) -> dict[str, tuple[float, float]]:
    candidate_ids = [str(node_id) for node_id in node_ids if node_id in fallback_pos]
    if not candidate_ids:
        return {}

    shared_ids = [node_id for node_id in candidate_ids if node_id in export_pos]

    if shared_ids:
        source_x = [fallback_pos[node_id][0] for node_id in shared_ids]
        source_y = [fallback_pos[node_id][1] for node_id in shared_ids]
        target_x = [export_pos[node_id][0] for node_id in shared_ids]
        target_y = [export_pos[node_id][1] for node_id in shared_ids]
    else:
        source_x = [fallback_pos[node_id][0] for node_id in candidate_ids]
        source_y = [fallback_pos[node_id][1] for node_id in candidate_ids]
        target_x = [export_pos[node_id][0] for node_id in export_pos]
        target_y = [export_pos[node_id][1] for node_id in export_pos]

    source_min_x, source_max_x = min(source_x), max(source_x)
    source_min_y, source_max_y = min(source_y), max(source_y)
    target_min_x, target_max_x = min(target_x), max(target_x)
    target_min_y, target_max_y = min(target_y), max(target_y)

    source_span_x = (source_max_x - source_min_x) or 1.0
    source_span_y = (source_max_y - source_min_y) or 1.0
    target_span_x = (target_max_x - target_min_x) or 1.0
    target_span_y = (target_max_y - target_min_y) or 1.0

    projected: dict[str, tuple[float, float]] = {}
    for node_id in candidate_ids:
        x_coord, y_coord = fallback_pos[node_id]
        projected[node_id] = (
            target_min_x + ((x_coord - source_min_x) / source_span_x) * target_span_x,
            target_min_y + ((y_coord - source_min_y) / source_span_y) * target_span_y,
        )
    return projected


def _compute_axis_limits(
    pos: dict[str, Any],
    *,
    margin_scale: float = DEFAULT_AXIS_MARGIN_SCALE,
) -> tuple[float, float, float, float]:
    if not pos:
        return (-1.0, 1.0, -1.0, 1.0)

    x_values = [coords[0] for coords in pos.values()]
    y_values = [coords[1] for coords in pos.values()]
    x_span = (max(x_values) - min(x_values)) or 1.0
    y_span = (max(y_values) - min(y_values)) or 1.0
    x_margin = margin_scale * x_span
    y_margin = margin_scale * y_span
    return (
        min(x_values) - x_margin,
        max(x_values) + x_margin,
        min(y_values) - y_margin,
        max(y_values) + y_margin,
    )


def _build_comparison_edges(
    network_links: Dict[str, Any],
    *,
    approach_type: str,
    baseline_type: str,
    display_ids: set[str],
    focus_ids: set[str],
) -> dict[str, list[tuple[str, str]]]:
    approach_edges = {
        _build_edge_key(edge.get("source"), edge.get("target"))
        for edge in get_links_by_type(network_links, approach_type)
        if (
            str(edge.get("source")) in display_ids
            and str(edge.get("target")) in display_ids
            and _edge_in_focus_neighborhood(str(edge.get("source")), str(edge.get("target")), focus_ids)
        )
    }
    baseline_edges = {
        _build_edge_key(edge.get("source"), edge.get("target"))
        for edge in get_links_by_type(network_links, baseline_type)
        if (
            str(edge.get("source")) in display_ids
            and str(edge.get("target")) in display_ids
            and _edge_in_focus_neighborhood(str(edge.get("source")), str(edge.get("target")), focus_ids)
        )
    }

    overlap = sorted(approach_edges & baseline_edges, key=lambda item: (int(item[0]), int(item[1])))
    approach_only = sorted(approach_edges - baseline_edges, key=lambda item: (int(item[0]), int(item[1])))
    baseline_only = sorted(baseline_edges - approach_edges, key=lambda item: (int(item[0]), int(item[1])))

    return {
        "approach_only": approach_only,
        "overlap": overlap,
        "baseline_only": baseline_only,
    }


def _build_type_legend_handles(graph: nx.DiGraph) -> list[Line2D]:
    group_attr = nx.get_node_attributes(graph, "group")
    group_counts = Counter(group_attr.values())
    handles = []

    ordered_groups = [group for group in TYPE_ORDER if group in group_counts]
    ordered_groups.extend(
        sorted(group for group in group_counts if group not in ordered_groups)
    )
    for group in ordered_groups:
        handles.append(
            Line2D(
                [],
                [],
                marker="o",
                color="w",
                label=f"{group} $(n={group_counts[group]})$",
                markerfacecolor=with_plot_alpha(_type_color(group)),
                markeredgecolor="black",
                markeredgewidth=0.9,
                markersize=10,
            )
        )

    return handles


def _build_edge_legend_handles(
    *,
    approach_type: str,
    baseline_type: str,
    comparison_edges: dict[str, list[tuple[str, str]]],
    edge_styles: dict[str, dict[str, Any]] | None = None,
    comparison_ordered: bool = False,
) -> list[Any]:
    approach_label = DEPENDENCY_APPROACH_SHORT_LABELS[approach_type]
    baseline_label = DEPENDENCY_APPROACH_SHORT_LABELS[baseline_type]
    styles = edge_styles or _build_edge_styles(comparison_ordered=comparison_ordered)

    if comparison_ordered:
        return [
            build_arrow_legend_handle(
                color=styles["overlap"]["color"],
                linestyle=styles["overlap"]["style"],
                linewidth=DIFF_EDGE_WIDTH,
                label=f"In both $({len(comparison_edges['overlap'])})$",
            ),
            build_arrow_legend_handle(
                color=styles["baseline_only"]["color"],
                linestyle=styles["baseline_only"]["style"],
                linewidth=DIFF_EDGE_WIDTH,
                label=f"Only in {baseline_label} $({len(comparison_edges['baseline_only'])})$",
            ),
            build_arrow_legend_handle(
                color=styles["approach_only"]["color"],
                linestyle=styles["approach_only"]["style"],
                linewidth=DIFF_EDGE_WIDTH,
                label=f"Only in {approach_label} $({len(comparison_edges['approach_only'])})$",
            ),
        ]

    return [
        build_arrow_legend_handle(
            color=styles["approach_only"]["color"],
            linestyle=styles["approach_only"]["style"],
            linewidth=DIFF_EDGE_WIDTH,
            label=f"{approach_label} only $(n={len(comparison_edges['approach_only'])})$",
        ),
        build_arrow_legend_handle(
            color=styles["overlap"]["color"],
            linestyle=styles["overlap"]["style"],
            linewidth=DIFF_EDGE_WIDTH,
            label=f"Also in {baseline_label} $(n={len(comparison_edges['overlap'])})$",
        ),
        build_arrow_legend_handle(
            color=styles["baseline_only"]["color"],
            linestyle=styles["baseline_only"]["style"],
            linewidth=DIFF_EDGE_WIDTH,
            label=f"Missing from {approach_label} $(n={len(comparison_edges['baseline_only'])})$",
        ),
    ]


def _compute_node_sizes(graph: nx.DiGraph, ordered_nodes: Sequence[str]) -> list[float]:
    degrees = dict(graph.degree())
    degree_values = [degrees.get(node_id, 0) for node_id in ordered_nodes]
    if not degree_values:
        return []

    min_degree = min(degree_values)
    max_degree = max(degree_values)
    if max_degree == min_degree:
        return [0.5 * (DIFF_NODE_SIZE_MIN + DIFF_NODE_SIZE_MAX)] * len(ordered_nodes)

    sizes = []
    for degree in degree_values:
        normalized = (degree - min_degree) / (max_degree - min_degree)
        sizes.append(DIFF_NODE_SIZE_MIN + normalized * (DIFF_NODE_SIZE_MAX - DIFF_NODE_SIZE_MIN))
    return sizes


def _compute_label_positions(pos: dict[str, Any], ordered_nodes: Sequence[str], node_sizes: Sequence[float]) -> dict[str, tuple[float, float, str, str]]:
    if not pos:
        return {}

    x_values = [coords[0] for coords in pos.values()]
    y_values = [coords[1] for coords in pos.values()]
    x_center = sum(x_values) / len(x_values)
    y_center = sum(y_values) / len(y_values)
    x_span = (max(x_values) - min(x_values)) or 1.0
    y_span = (max(y_values) - min(y_values)) or 1.0
    diag = math.hypot(x_span, y_span) or 1.0

    label_positions: dict[str, tuple[float, float, str, str]] = {}
    for node_id, node_size in zip(ordered_nodes, node_sizes):
        x_coord, y_coord = pos[node_id]
        dx = x_coord - x_center
        dy = y_coord - y_center
        norm = math.hypot(dx, dy)
        if norm < 1e-9:
            dx, dy = 1.0, 1.0
            norm = math.hypot(dx, dy)
        unit_x = dx / norm
        unit_y = dy / norm
        radial_offset = DIFF_LABEL_OFFSET * diag + 0.00003 * node_size
        label_x = x_coord + unit_x * radial_offset
        label_y = y_coord + unit_y * radial_offset
        label_positions[node_id] = (
            label_x,
            label_y,
            "left" if unit_x >= 0 else "right",
            "bottom" if unit_y >= 0 else "top",
        )

    return label_positions


def _edge_connectionstyle(
    edge: tuple[str, str],
    all_edges: set[tuple[str, str]],
    *,
    layout_name: str,
) -> str:
    source_id, target_id = edge
    override = EDGE_CURVATURE_OVERRIDES.get((str(source_id), str(target_id)))
    if override is not None:
        return f"arc3,rad={override}"

    is_reciprocal = (target_id, source_id) in all_edges

    _ = layout_name
    curvature = RECIPROCAL_EDGE_CURVATURE if is_reciprocal else EDGE_CURVATURE
    return f"arc3,rad={curvature}"


def _draw_comparison_plot(
    ax: plt.Axes,
    graph: nx.DiGraph,
    pos: dict[str, Any],
    axis_limits: tuple[float, float, float, float],
    *,
    comparison_edges: dict[str, list[tuple[str, str]]],
    approach_type: str,
    baseline_type: str,
    layout_name: str,
    title: str,
    edge_styles: dict[str, dict[str, Any]] | None = None,
    title_fontsize: float | None = None,
    title_pad: float = 20,
) -> None:
    if graph.number_of_nodes() == 0:
        return

    ordered_nodes = sorted(graph.nodes(), key=int)
    node_groups = nx.get_node_attributes(graph, "group")
    node_colors = [
        with_plot_alpha(_type_color(node_groups.get(node_id, "Unknown Type")), NODE_FILL_ALPHA)
        for node_id in ordered_nodes
    ]
    node_sizes = _compute_node_sizes(graph, ordered_nodes)
    styles = edge_styles or _build_edge_styles()

    ax.set_xlim(axis_limits[0], axis_limits[1])
    ax.set_ylim(axis_limits[2], axis_limits[3])
    ax.set_aspect("equal", adjustable="box")

    nx.draw_networkx_nodes(
        graph,
        pos,
        nodelist=ordered_nodes,
        node_size=node_sizes,
        node_color=node_colors,
        alpha=None,
        edgecolors="black",
        linewidths=1.0,
        ax=ax,
    )

    all_edges = {
        edge
        for edgelist in comparison_edges.values()
        for edge in edgelist
    }
    for status, edgelist in comparison_edges.items():
        if not edgelist:
            continue
        style_info = styles[status]
        for edge in edgelist:
            connectionstyle = _edge_connectionstyle(edge, all_edges, layout_name=layout_name)
            nx.draw_networkx_edges(
                graph,
                pos,
                edgelist=[edge],
                edge_color=style_info["color"],
                style=style_info["style"],
                width=DIFF_EDGE_WIDTH,
                alpha=style_info["alpha"],
                arrows=True,
                arrowstyle="-",
                arrowsize=DIFF_ARROW_SIZE,
                node_size=node_sizes,
                nodelist=ordered_nodes,
                node_shape="o",
                connectionstyle=connectionstyle,
                min_source_margin=0,
                min_target_margin=0,
                ax=ax,
            )
            nx.draw_networkx_edges(
                graph,
                pos,
                edgelist=[edge],
                edge_color=style_info["color"],
                style="solid",
                width=DIFF_ARROWHEAD_OVERLAY_WIDTH,
                alpha=style_info["alpha"],
                arrows=True,
                arrowstyle="-|>",
                arrowsize=DIFF_ARROW_SIZE,
                node_size=node_sizes,
                nodelist=ordered_nodes,
                node_shape="o",
                connectionstyle=connectionstyle,
                min_source_margin=0,
                min_target_margin=0,
                ax=ax,
            )

    for node_id in ordered_nodes:
        label_text = f"{int(node_id)}"
        x, y = pos[node_id]
        ax.text(
            x,
            y,
            label_text,
            fontsize=NODE_LABEL_FONT_SIZE,
            fontweight="bold",
            family="monospace",
            ha="center",
            va="center",
            color="black",
            zorder=5,
        )

    ax.set_title(title, pad=title_pad, y=1.0, fontsize=title_fontsize)
    ax.axis("off")


def _save_single_comparison_plot(
    graph: nx.DiGraph,
    pos: dict[str, Any],
    axis_limits: tuple[float, float, float, float],
    *,
    comparison_edges: dict[str, list[tuple[str, str]]],
    approach_type: str,
    baseline_type: str,
    layout_name: str,
    title: str,
    output_path: Path,
) -> None:
    if graph.number_of_nodes() == 0:
        return

    fig, ax = plt.subplots(figsize=SINGLE_COMPARISON_FIGSIZE)
    _draw_comparison_plot(
        ax,
        graph,
        pos,
        axis_limits,
        comparison_edges=comparison_edges,
        approach_type=approach_type,
        baseline_type=baseline_type,
        layout_name=layout_name,
        title=title,
        edge_styles=_build_edge_styles(),
    )

    legend_handles = _build_type_legend_handles(graph) + _build_edge_legend_handles(
        approach_type=approach_type,
        baseline_type=baseline_type,
        comparison_edges=comparison_edges,
        edge_styles=_build_edge_styles(),
    )
    if legend_handles:
        ncol = math.ceil(len(legend_handles) / 2)
        ax.legend(
            handles=legend_handles,
            loc="lower center",
            bbox_to_anchor=(0.5, 0.95),
            ncol=ncol,
            handler_map=ARROW_LEGEND_HANDLER_MAP,
            frameon=False,
            fancybox=False,
            shadow=False,
            fontsize=8.5,
            handlelength=1.9,
            columnspacing=1.0,
            handletextpad=0.35,
            labelspacing=0.5,
        )

    fig.tight_layout(rect=[0, 0, 1, 0.99])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, format="pdf")
    plt.close(fig)


def _save_combined_comparison_plot(
    graph: nx.DiGraph,
    pos: dict[str, Any],
    axis_limits: tuple[float, float, float, float],
    *,
    plot_payloads: Sequence[dict[str, Any]],
    layout_name: str,
    output_path: Path,
) -> None:
    if graph.number_of_nodes() == 0 or not plot_payloads:
        return

    fig, axes = plt.subplots(1, len(plot_payloads), figsize=COMBINED_COMPARISON_FIGSIZE)
    if hasattr(axes, "flat"):
        axes = list(axes.flat)
    else:
        axes = [axes]

    combined_edge_styles = _build_edge_styles(comparison_ordered=True)
    for index, (ax, payload) in enumerate(zip(axes, plot_payloads), start=1):
        _draw_comparison_plot(
            ax,
            graph,
            pos,
            axis_limits,
            comparison_edges=payload["comparison_edges"],
            approach_type=payload["approach_type"],
            baseline_type=payload["baseline_type"],
            layout_name=layout_name,
            title=f"({chr(96 + index)}) {payload['subplot_title']}",
            edge_styles=combined_edge_styles,
            title_fontsize=COMBINED_SUBPLOT_TITLE_FONT_SIZE,
            title_pad=COMBINED_SUBPLOT_TITLE_PAD,
        )
        edge_legend_handles = _build_edge_legend_handles(
            approach_type=payload["approach_type"],
            baseline_type=payload["baseline_type"],
            comparison_edges=payload["comparison_edges"],
            edge_styles=combined_edge_styles,
            comparison_ordered=True,
        )
        ax.legend(
            handles=edge_legend_handles,
            loc="upper center",
            bbox_to_anchor=(0.5, 0.07),
            ncol=3,
            handler_map=ARROW_LEGEND_HANDLER_MAP,
            frameon=False,
            fancybox=False,
            shadow=False,
            fontsize=COMBINED_EDGE_LEGEND_FONT_SIZE,
            handlelength=1.9,
            columnspacing=0.85,
            handletextpad=0.35,
            labelspacing=0.5,
            title="Edges",
            title_fontsize=COMBINED_EDGE_LEGEND_TITLE_FONT_SIZE,
        )

    type_handles = _build_type_legend_handles(graph)
    if type_handles:
        fig.legend(
            handles=type_handles,
            loc="upper center",
            bbox_to_anchor=(0.5, 0.85),
            ncol=3,
            frameon=False,
            fancybox=False,
            fontsize=COMBINED_NODE_LEGEND_FONT_SIZE,
            columnspacing=1.0,
            handletextpad=0.2,
            labelspacing=0.5,
            title="Nodes",
            title_fontsize=COMBINED_NODE_LEGEND_TITLE_FONT_SIZE,
        )

    fig.tight_layout(rect=[0.015, 0.13, 0.985, 0.87], w_pad=-2)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, format="pdf")
    plt.close(fig)


def render_differential_dependency_plots(
    network_data: Dict[str, Any],
    output_dir: Path,
    *,
    filename_prefix: str | None = None,
    focus_bips: Sequence[int | str] = DEFAULT_FOCUS_BIPS,
    exclude_bips: Sequence[int | str] | None = DEFAULT_EXCLUDE_BIPS,
    layout_name: str = DEFAULT_LAYOUT_NAME,
    layout_export_path: Path | None = None,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    display_ids, focus_ids = _collect_display_node_ids(network_data, focus_bips, exclude_bips)
    layout_graph = _build_layout_graph(network_data, display_ids, focus_ids)

    # Keep one shared union-layout graph so both plots inherit identical node positions.
    if layout_export_path is not None:
        exported_pos = _load_exported_positions(layout_export_path, layout_graph.nodes())
        if not exported_pos:
            base_pos = _compute_base_positions(layout_graph, layout_name=DEFAULT_LAYOUT_NAME)
        else:
            missing_ids = sorted((str(node_id) for node_id in layout_graph.nodes() if str(node_id) not in exported_pos), key=int)
            if missing_ids:
                fallback_pos = _compute_base_positions(layout_graph, layout_name=DEFAULT_LAYOUT_NAME)
                projected_fallback = _project_fallback_positions_into_export_space(
                    fallback_pos,
                    exported_pos,
                    layout_graph.nodes(),
                )
                base_pos = {
                    **{node_id: projected_fallback[node_id] for node_id in missing_ids if node_id in projected_fallback},
                    **exported_pos,
                }
            else:
                base_pos = exported_pos
        pos = base_pos
    else:
        base_pos = _compute_base_positions(layout_graph, layout_name=layout_name)
        pos = _compact_positions(base_pos, compaction=_get_layout_compaction(layout_name))
    axis_limits = _compute_axis_limits(base_pos)
    combined_axis_limits = _compute_axis_limits(base_pos, margin_scale=COMBINED_AXIS_MARGIN_SCALE)

    plot_payloads: list[dict[str, Any]] = []
    output_paths: list[Path] = []
    for plot_spec in COMPARISON_PLOTS:
        comparison_edges = _build_comparison_edges(
            network_data.get("links", {}),
            approach_type=plot_spec["approach"],
            baseline_type=plot_spec["baseline"],
            display_ids=display_ids,
            focus_ids=focus_ids,
        )
        plot_payloads.append(
            {
                "comparison_edges": comparison_edges,
                "approach_type": plot_spec["approach"],
                "baseline_type": plot_spec["baseline"],
                "subplot_title": plot_spec.get("subplot_title", plot_spec["title"]),
            }
        )
        prefix = f"{filename_prefix}_" if filename_prefix else ""
        output_path = output_dir / f"{prefix}diffdep_{layout_name}_{plot_spec['filename_stem']}.pdf"
        _save_single_comparison_plot(
            layout_graph,
            pos,
            axis_limits,
            comparison_edges=comparison_edges,
            approach_type=plot_spec["approach"],
            baseline_type=plot_spec["baseline"],
            layout_name=layout_name,
            title=plot_spec["title"],
            output_path=output_path,
        )
        output_paths.append(output_path)

    if layout_export_path is not None and len(plot_payloads) > 1:
        prefix = f"{filename_prefix}_" if filename_prefix else ""
        combined_output_path = output_dir / f"{prefix}diffdep_{layout_name}_{COMBINED_REACT_DIFFDEP_FILENAME_STEM}.pdf"
        _save_combined_comparison_plot(
            layout_graph,
            pos,
            combined_axis_limits,
            plot_payloads=plot_payloads,
            layout_name=layout_name,
            output_path=combined_output_path,
        )
        output_paths.append(combined_output_path)

    return output_paths


def _parse_bips_argument(raw_value: str | None) -> list[int]:
    if not raw_value:
        return DEFAULT_FOCUS_BIPS
    return [int(match.group(0)) for match in re.finditer(r"\d+", raw_value)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Render differential dependency comparison plots for RQ2.")
    parser.add_argument("--snapshot", default=SNAPSHOT, help="Snapshot label to load, defaults to paper.config.SNAPSHOT.")
    parser.add_argument("--output-dir", default=None, help="Optional output directory override.")
    parser.add_argument(
        "--layout-export",
        default=None,
        help="Optional path to a JSON layout export downloaded from the React network card.",
    )
    parser.add_argument(
        "--layout-export-label",
        default="react_export",
        help="Filename layout label to use when --layout-export is provided.",
    )
    parser.add_argument(
        "--bips",
        default=",".join(str(bip) for bip in DEFAULT_FOCUS_BIPS),
        help="Comma-separated focus BIP ids used to define the local comparison neighborhood.",
    )
    parser.add_argument(
        "--exclude-bips",
        default=",".join(str(bip) for bip in DEFAULT_EXCLUDE_BIPS),
        help="Comma-separated BIP ids to exclude from the plotted local neighborhood.",
    )
    parser.add_argument(
        "--layout",
        default=DEFAULT_LAYOUT_NAME,
        choices=["spring_default", "spring_spread", "spring_scaled", "planar", "spectral", "shell", "circular", "bipartite", "multipartite", "kamada_kawai"],
        help="Layout algorithm for the shared node positions.",
    )
    args = parser.parse_args()

    snapshot_label = args.snapshot or resolve_latest_snapshot_label() or "latest"
    output_dir = resolve_output_dir(args.output_dir, DEFAULT_OUTPUT_DIR)

    network_data = load_network_data(snapshot=args.snapshot)
    render_differential_dependency_plots(
        network_data,
        output_dir=output_dir,
        filename_prefix=snapshot_prefix(snapshot_label),
        focus_bips=_parse_bips_argument(args.bips),
        exclude_bips=_parse_bips_argument(args.exclude_bips),
        layout_name=args.layout_export_label if args.layout_export else args.layout,
        layout_export_path=Path(args.layout_export) if args.layout_export else None,
    )


if __name__ == "__main__":
    main()
