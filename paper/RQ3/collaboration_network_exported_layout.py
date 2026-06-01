import argparse
import json
import math
import sys
from collections.abc import Sequence as SequenceABC
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.colors import to_rgba

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis.artifact_io import load_authorship_payload, load_network_data, resolve_latest_snapshot_label
from paper.RQ3._plotting import save_figure
from paper.RQ3.collaboration_common import build_author_bip_map
from paper._utils.io import resolve_output_dir, snapshot_prefix
from paper.config import SNAPSHOT
from paper.plot_colors import ORDERED_PLOT_PALETTE, PLOT_COLOR_ALPHA


LAYOUT_EXPORT_DIR = Path("paper") / "RQ3"
LAYOUT_EXPORT_FILENAME = "authorship_layout_260316_balanced"
DEFAULT_OUTPUT_DIR = Path("paper") / "RQ3" / "outputs"
DEFAULT_FIGSIZE = (11,6)
DEFAULT_AXIS_MARGIN_SCALE = 0.08
EDGE_WIDTH_RANGE = (1.2, 5.0)
NODE_RADIUS_RANGE = (6.0, 18.0)
NODE_FILL_ALPHA = PLOT_COLOR_ALPHA
NODE_BORDER_COLOR = "#111111"
NODE_BORDER_WIDTH = 1.5
EDGE_ALPHA = 0.7
EDGE_CURVATURE = 0.08
DEFAULT_EDGE_CURVE_DIRECTION = 1
DEFAULT_EDGE_CURVE_STRENGTH = 1.0
NODE_LABEL_MIN_BIP_COUNT = 3
NODE_LABEL_MIN_DEGREE = 3
NODE_LABEL_FONT_SIZE = 9.5
NODE_LABEL_BOX_ALPHA = 0.6
COLLABORATION_CLUSTER_COLORS = ORDERED_PLOT_PALETTE


def _sanitize_file_part(value: Any, fallback: str = "unknown") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback

    sanitized = []
    last_was_dash = False
    for char in text:
        if char.isalnum() or char in {".", "_"}:
            sanitized.append(char)
            last_was_dash = False
            continue

        if not last_was_dash:
            sanitized.append("-")
            last_was_dash = True

    out = "".join(sanitized).strip("-")
    return out or fallback


def _normalize_imported_positions(payload: dict[str, Any]) -> dict[str, tuple[float, float]]:
    normalized_positions: dict[str, tuple[float, float]] = {}
    raw_positions = payload.get("positions")

    if isinstance(raw_positions, dict):
        for node_id, coords in raw_positions.items():
            if isinstance(coords, SequenceABC) and len(coords) >= 2:
                x_coord = float(coords[0])
                y_coord = float(coords[1])
                normalized_positions[str(node_id)] = (x_coord, y_coord)

    if normalized_positions:
        return normalized_positions

    for node in payload.get("nodes", []):
        node_id = node.get("id")
        x_coord = node.get("x")
        y_coord = node.get("y")
        if node_id is None or x_coord is None or y_coord is None:
            continue
        normalized_positions[str(node_id)] = (float(x_coord), float(y_coord))

    return normalized_positions


def _build_canonical_edge_key(source_id: str, target_id: str) -> str:
    left = str(source_id)
    right = str(target_id)
    if left <= right:
        return f"{left}\0{right}"
    return f"{right}\0{left}"


def _normalize_imported_edge_curves(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    normalized_curves: dict[str, dict[str, Any]] = {}
    raw_curves = payload.get("edge_curves")
    if not isinstance(raw_curves, list):
        return normalized_curves

    for entry in raw_curves:
        if not isinstance(entry, dict):
            continue

        source_id = str(entry.get("source") or "").strip()
        target_id = str(entry.get("target") or "").strip()
        if not source_id or not target_id or source_id == target_id:
            continue

        raw_direction = entry.get("direction")
        direction = -1 if isinstance(raw_direction, (int, float)) and float(raw_direction) < 0 else DEFAULT_EDGE_CURVE_DIRECTION

        raw_strength = entry.get("strength")
        strength = (
            float(raw_strength)
            if isinstance(raw_strength, (int, float)) and float(raw_strength) > 0
            else DEFAULT_EDGE_CURVE_STRENGTH
        )

        normalized_curves[_build_canonical_edge_key(source_id, target_id)] = {
            "source": source_id,
            "target": target_id,
            "direction": direction,
            "strength": strength,
        }

    return normalized_curves


def resolve_layout_export_path(layout_export_value: str | None) -> Path:
    if layout_export_value is not None and str(layout_export_value).strip():
        candidate = Path(str(layout_export_value).strip())
        if candidate.suffix:
            return candidate
        return candidate.with_suffix(".json")

    default_candidate = LAYOUT_EXPORT_DIR / LAYOUT_EXPORT_FILENAME
    if default_candidate.suffix:
        return default_candidate
    return default_candidate.with_suffix(".json")


def _build_display_collaboration_components(nodes: list[dict[str, Any]], adjacency: dict[str, set[str]]) -> list[list[str]]:
    isolated_ids: list[str] = []
    visited: set[str] = set()
    components: list[list[str]] = []

    for node in nodes:
        node_id = str(node.get("id"))
        neighbors = adjacency.get(node_id, set())
        if len(neighbors) == 0:
            isolated_ids.append(node_id)
            continue

        if node_id in visited:
            continue

        queue = [node_id]
        members: list[str] = []
        visited.add(node_id)

        while queue:
            current = queue.pop(0)
            members.append(current)

            for neighbor in adjacency.get(current, set()):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append(neighbor)

        components.append(members)

    components.sort(key=len, reverse=True)

    if isolated_ids:
        components.append(sorted(isolated_ids))

    return components


def _compute_axis_limits(
    positions: dict[str, tuple[float, float]],
    *,
    margin_scale: float = DEFAULT_AXIS_MARGIN_SCALE,
) -> tuple[float, float, float, float]:
    if not positions:
        return (-1.0, 1.0, -1.0, 1.0)

    x_values = [coords[0] for coords in positions.values()]
    y_values = [coords[1] for coords in positions.values()]
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


def _sqrt_scaled_value(
    value: float,
    *,
    domain_min: float,
    domain_max: float,
    range_min: float,
    range_max: float,
) -> float:
    if domain_max <= domain_min:
        return (range_min + range_max) * 0.5

    clamped_value = min(max(value, domain_min), domain_max)
    domain_span = math.sqrt(domain_max) - math.sqrt(domain_min)
    if domain_span <= 0:
        return (range_min + range_max) * 0.5

    fraction = (math.sqrt(clamped_value) - math.sqrt(domain_min)) / domain_span
    return range_min + fraction * (range_max - range_min)


def _linear_scaled_value(
    value: float,
    *,
    domain_min: float,
    domain_max: float,
    range_min: float,
    range_max: float,
) -> float:
    if domain_max <= domain_min:
        return (range_min + range_max) * 0.5

    clamped_value = min(max(value, domain_min), domain_max)
    fraction = (clamped_value - domain_min) / (domain_max - domain_min)
    return range_min + fraction * (range_max - range_min)


def _should_draw_node_label(node_attrs: dict[str, Any]) -> bool:
    bip_count = int(node_attrs.get("bip_count", 0) or 0)
    degree = int(node_attrs.get("degree", 0) or 0)
    return bip_count >= NODE_LABEL_MIN_BIP_COUNT or degree >= NODE_LABEL_MIN_DEGREE


def _resolve_edge_curve(source_id: str, target_id: str, edge_curve_overrides: dict[str, dict[str, Any]]) -> dict[str, Any]:
    curve = edge_curve_overrides.get(_build_canonical_edge_key(source_id, target_id))
    if curve is not None:
        return curve

    return {
        "source": source_id,
        "target": target_id,
        "direction": DEFAULT_EDGE_CURVE_DIRECTION,
        "strength": DEFAULT_EDGE_CURVE_STRENGTH,
    }


def _build_visible_graph(
    network_data: dict[str, Any],
    authorship_payload: dict[str, Any],
    layout_payload: dict[str, Any],
) -> tuple[nx.Graph, dict[str, tuple[float, float]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    collaboration_network = authorship_payload.get("collaboration_network", {}) or {}
    raw_nodes = collaboration_network.get("nodes", []) or []
    raw_edges = collaboration_network.get("edges", []) or []
    author_bip_map = build_author_bip_map(network_data)
    exported_positions = _normalize_imported_positions(layout_payload)
    edge_curve_overrides = _normalize_imported_edge_curves(layout_payload)
    if not exported_positions:
        raise ValueError("Layout export does not contain any node positions.")

    raw_node_ids = {
        str(node.get("id"))
        for node in raw_nodes
        if node.get("id") is not None
    }
    display_node_ids = {
        node_id
        for node_id in exported_positions
        if node_id in raw_node_ids
    }
    if not display_node_ids:
        raise ValueError("No exported layout nodes matched the authorship collaboration network.")

    adjacency: dict[str, set[str]] = {
        str(node.get("id")): set()
        for node in raw_nodes
        if node.get("id") is not None
    }
    for edge in raw_edges:
        source_id = str(edge.get("source"))
        target_id = str(edge.get("target"))
        if source_id not in adjacency or target_id not in adjacency:
            continue
        adjacency[source_id].add(target_id)
        adjacency[target_id].add(source_id)

    components = _build_display_collaboration_components(raw_nodes, adjacency)
    cluster_meta: list[dict[str, Any]] = []
    for cluster_index, members in enumerate(components):
        member_ids = set(members)
        edge_count = sum(
            1
            for edge in raw_edges
            if str(edge.get("source")) in member_ids and str(edge.get("target")) in member_ids
        )
        cluster_meta.append(
            {
                "clusterId": cluster_index,
                "members": members,
                "clusterSize": len(members),
                "edgeCount": edge_count,
            }
        )

    cluster_by_node_id: dict[str, dict[str, int]] = {}
    for cluster in cluster_meta:
        for member in cluster["members"]:
            cluster_by_node_id[member] = {
                "clusterId": int(cluster["clusterId"]),
                "clusterSize": int(cluster["clusterSize"]),
                "clusterCollaborations": int(cluster["edgeCount"]),
            }

    filtered_cluster_ids = {
        cluster_by_node_id[node_id]["clusterId"]
        for node_id in display_node_ids
        if node_id in cluster_by_node_id
    }
    visible_clusters = [
        cluster
        for cluster in cluster_meta
        if int(cluster["clusterId"]) in filtered_cluster_ids
    ]
    cluster_color_by_id = {
        int(cluster["clusterId"]): COLLABORATION_CLUSTER_COLORS[index % len(COLLABORATION_CLUSTER_COLORS)]
        for index, cluster in enumerate(visible_clusters)
    }

    graph = nx.Graph()
    for node in raw_nodes:
        node_id = str(node.get("id"))
        if node_id not in display_node_ids:
            continue

        cluster = cluster_by_node_id.get(node_id, {"clusterId": -1, "clusterSize": 1, "clusterCollaborations": 0})
        graph.add_node(
            node_id,
            degree=int(node.get("degree", 0) or 0),
            bip_count=len(author_bip_map.get(node_id, [])),
            cluster_id=int(cluster["clusterId"]),
            cluster_size=int(cluster["clusterSize"]),
            cluster_collaborations=int(cluster["clusterCollaborations"]),
            cluster_color=cluster_color_by_id.get(int(cluster["clusterId"]), COLLABORATION_CLUSTER_COLORS[0]),
        )

    for edge in raw_edges:
        source_id = str(edge.get("source"))
        target_id = str(edge.get("target"))
        if source_id not in display_node_ids or target_id not in display_node_ids:
            continue

        graph.add_edge(
            source_id,
            target_id,
            weight=int(edge.get("weight", 1) or 1),
            raw_source=source_id,
            raw_target=target_id,
        )

    visible_positions = {
        node_id: exported_positions[node_id]
        for node_id in graph.nodes()
        if node_id in exported_positions
    }
    if not visible_positions:
        raise ValueError("No graph nodes remained after applying exported layout positions.")

    return graph, visible_positions, visible_clusters, edge_curve_overrides


def plot_collaboration_network_from_exported_layout(
    network_data: dict[str, Any],
    authorship_payload: dict[str, Any],
    layout_export_path: Path,
    output_path: Path,
    snapshot_label: str,
    *,
    title: str | None = None,
) -> None:
    layout_payload = json.loads(layout_export_path.read_text(encoding="utf8"))
    graph, positions, visible_clusters, edge_curve_overrides = _build_visible_graph(
        network_data,
        authorship_payload,
        layout_payload,
    )
    if graph.number_of_nodes() == 0:
        raise ValueError("Exported collaboration graph is empty.")

    ordered_nodes = sorted(
        graph.nodes(),
        key=lambda author: (
            -int(graph.nodes[author].get("bip_count", 0) or 0),
            -int(graph.nodes[author].get("degree", 0) or 0),
            author.lower(),
        ),
    )
    bip_count_values = [int(graph.nodes[node_id].get("bip_count", 0) or 0) for node_id in ordered_nodes]
    bip_count_min = min(bip_count_values) if bip_count_values else 0
    bip_count_max = max(bip_count_values) if bip_count_values else 1
    node_radii = {
        node_id: _sqrt_scaled_value(
            float(graph.nodes[node_id].get("bip_count", 0) or 0),
            domain_min=float(bip_count_min),
            domain_max=float(bip_count_max if bip_count_max > bip_count_min else bip_count_min + 1),
            range_min=NODE_RADIUS_RANGE[0],
            range_max=NODE_RADIUS_RANGE[1],
        )
        for node_id in ordered_nodes
    }
    node_sizes = [math.pi * (node_radii[node_id] ** 2) for node_id in ordered_nodes]

    edge_list = sorted(
        graph.edges(data=True),
        key=lambda item: (
            -int(item[2].get("weight", 1) or 1),
            str(item[2].get("raw_source") or item[0]).lower(),
            str(item[2].get("raw_target") or item[1]).lower(),
        ),
    )
    edge_weights = [int(data.get("weight", 1) or 1) for _, _, data in edge_list]
    weight_min = min(edge_weights) if edge_weights else 1
    weight_max = max(edge_weights) if edge_weights else 1
    edge_widths = [
        _linear_scaled_value(
            float(data.get("weight", 1) or 1),
            domain_min=float(weight_min),
            domain_max=float(weight_max if weight_max > weight_min else weight_min + 1),
            range_min=EDGE_WIDTH_RANGE[0],
            range_max=EDGE_WIDTH_RANGE[1],
        )
        for _, _, data in edge_list
    ]
    edge_colors = [
        to_rgba(
            graph.nodes[str(data.get("raw_source") or source_id)].get(
                "cluster_color",
                COLLABORATION_CLUSTER_COLORS[0],
            ),
            EDGE_ALPHA,
        )
        for source_id, _, data in edge_list
    ]

    figure, axis = plt.subplots(figsize=DEFAULT_FIGSIZE)
    axis_limits = _compute_axis_limits(positions)
    axis.set_xlim(axis_limits[0], axis_limits[1])
    axis.set_ylim(axis_limits[2], axis_limits[3])
    axis.set_aspect("equal", adjustable="box")

    if edge_list:
        for (source_id, target_id, data), edge_width, edge_color in zip(edge_list, edge_widths, edge_colors):
            edge_source = str(data.get("raw_source") or source_id)
            edge_target = str(data.get("raw_target") or target_id)
            curve = _resolve_edge_curve(edge_source, edge_target, edge_curve_overrides)
            orientation_matches = (
                1
                if curve.get("source") == edge_source and curve.get("target") == edge_target
                else -1
            )
            signed_curvature = (
                EDGE_CURVATURE
                * float(curve.get("direction", DEFAULT_EDGE_CURVE_DIRECTION))
                * orientation_matches
                * float(curve.get("strength", DEFAULT_EDGE_CURVE_STRENGTH))
            )

            nx.draw_networkx_edges(
                graph,
                positions,
                edgelist=[(edge_source, edge_target)],
                width=edge_width,
                edge_color=[edge_color],
                alpha=None,
                arrows=True,
                arrowstyle="-",
                connectionstyle=f"arc3,rad={signed_curvature}",
                ax=axis,
            )

    nx.draw_networkx_nodes(
        graph,
        positions,
        nodelist=ordered_nodes,
        node_size=node_sizes,
        node_color=[
            to_rgba(graph.nodes[node_id].get("cluster_color", COLLABORATION_CLUSTER_COLORS[0]), NODE_FILL_ALPHA)
            for node_id in ordered_nodes
        ],
        edgecolors=NODE_BORDER_COLOR,
        linewidths=NODE_BORDER_WIDTH,
        ax=axis,
    )

    for node_id in ordered_nodes:
        node_attrs = graph.nodes[node_id]
        if not _should_draw_node_label(node_attrs):
            continue

        x_coord, y_coord = positions[node_id]
        text = axis.text(
            x_coord + node_radii[node_id] + 4.0,
            y_coord + 1.5,
            node_id,
            fontsize=NODE_LABEL_FONT_SIZE,
            ha="left",
            va="center",
            color="#111111",
            zorder=6,
            bbox={
                "boxstyle": "round,pad=0.16",
                "facecolor": "white",
                "edgecolor": "none",
                "alpha": NODE_LABEL_BOX_ALPHA,
            },
        )

    layout_mode = str(layout_payload.get("layout_mode") or "layout").strip() or "layout"
    cluster_count = len(visible_clusters)
    default_title = f"Collaboration Network ({snapshot_label}, {layout_mode}, {cluster_count} clusters)"
    axis.set_title(title or default_title, pad=14)
    axis.axis("off")
    figure.tight_layout()
    save_figure(figure, output_path)


def resolve_default_output_path(
    *,
    snapshot_label: str,
    layout_payload: dict[str, Any],
    output_dir: Path,
) -> Path:
    layout_mode = _sanitize_file_part(layout_payload.get("layout_mode"), "layout")
    filename_prefix = snapshot_prefix(snapshot_label)
    return output_dir / f"{filename_prefix}_collaboration_network_exported_{layout_mode}.pdf"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render a static collaboration network figure from an exported authorship layout JSON."
    )
    parser.add_argument(
        "--layout-export",
        help="Optional path to an exported authorship layout JSON file. Defaults to the module-level LAYOUT_EXPORT_FILENAME.",
    )
    parser.add_argument(
        "--snapshot",
        default=SNAPSHOT,
        help="Snapshot label to load authorship payload from. Defaults to paper.config.SNAPSHOT or the layout file snapshot.",
    )
    parser.add_argument(
        "--output",
        help="Optional explicit PDF output path.",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional output directory used when --output is omitted.",
    )
    parser.add_argument(
        "--title",
        help="Optional custom plot title.",
    )
    args = parser.parse_args()

    layout_export_path = resolve_layout_export_path(args.layout_export)
    layout_payload = json.loads(layout_export_path.read_text(encoding="utf8"))
    snapshot_label = (
        str(args.snapshot).strip()
        if args.snapshot is not None and str(args.snapshot).strip()
        else str(layout_payload.get("snapshot") or "").strip()
    )
    if not snapshot_label:
        snapshot_label = resolve_latest_snapshot_label() or "latest"

    network_data = load_network_data(snapshot=snapshot_label)
    authorship_payload = load_authorship_payload(snapshot=snapshot_label)
    output_dir = resolve_output_dir(args.output_dir, DEFAULT_OUTPUT_DIR)
    output_path = Path(args.output) if args.output else resolve_default_output_path(
        snapshot_label=snapshot_label,
        layout_payload=layout_payload,
        output_dir=output_dir,
    )

    plot_collaboration_network_from_exported_layout(
        network_data=network_data,
        authorship_payload=authorship_payload,
        layout_export_path=layout_export_path,
        output_path=output_path,
        snapshot_label=snapshot_label,
        title=args.title,
    )


if __name__ == "__main__":
    main()
