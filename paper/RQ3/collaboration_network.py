import math
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx

from paper.plot_colors import PLOT_COLOR_ALPHA, with_plot_alpha
from paper.RQ3._plotting import save_figure
from paper.RQ3.collaboration_common import build_author_bip_map


CLUSTER_COLORS = [
    "#2a6f97",
    "#bc4749",
    "#6a994e",
    "#7b2cbf",
    "#f4a261",
    "#457b9d",
    "#e76f51",
    "#8d99ae",
    "#2b9348",
    "#ffb703",
    "#577590",
    "#c77dff",
]
COLLABORATION_LAYOUTS = [
    "kamada_kawai",
]


def _build_layout_graph(graph: nx.Graph) -> nx.Graph:
    layout_graph = graph.copy()
    for _, _, data in layout_graph.edges(data=True):
        weight = float(data.get("weight", 1) or 1)
        data["layout_weight"] = 0.2 + math.sqrt(weight) * 0.16
    return layout_graph


def _stretch_positions(
    positions: dict[str, tuple[float, float]],
    scale_x: float = 2.05,
    scale_y: float = 1.28,
) -> dict[str, tuple[float, float]]:
    return {
        node_id: (x * scale_x, y * scale_y)
        for node_id, (x, y) in positions.items()
    }


def _build_layout(graph: nx.Graph, layout_name: str) -> dict[str, tuple[float, float]]:
    if graph.number_of_nodes() == 0:
        return {}

    if graph.number_of_nodes() == 1:
        return {next(iter(graph.nodes())): (0.0, 0.0)}

    layout_graph = _build_layout_graph(graph)

    if layout_name == "spring":
        positions = nx.spring_layout(
            layout_graph,
            seed=42,
            weight="layout_weight",
            k=78 / math.sqrt(graph.number_of_nodes()),
            iterations=1000,
            scale=14.0,
        )
        return _stretch_positions(positions)

    if layout_name == "kamada_kawai":
        positions = nx.kamada_kawai_layout(
            layout_graph,
            weight="layout_weight",
            scale=12.0,
        )
        return _stretch_positions(positions, scale_x=1.7, scale_y=1.2)

    if layout_name == "spectral":
        positions = nx.spectral_layout(
            layout_graph,
            weight="layout_weight",
            scale=12.0,
        )
        return _stretch_positions(positions, scale_x=2.1, scale_y=1.25)

    if layout_name == "circular":
        positions = nx.circular_layout(layout_graph, scale=12.0)
        return _stretch_positions(positions, scale_x=1.8, scale_y=1.1)

    if layout_name == "spiral":
        positions = nx.spiral_layout(layout_graph, scale=12.0)
        return _stretch_positions(positions, scale_x=1.65, scale_y=1.15)

    if layout_name == "shell":
        positions = nx.shell_layout(layout_graph, scale=12.0)
        return _stretch_positions(positions, scale_x=1.7, scale_y=1.1)

    raise ValueError(f"Unsupported collaboration layout: {layout_name}")


def _resolve_node_overlaps(
    positions: dict[str, tuple[float, float]],
    node_radius_by_author: dict[str, float],
    iterations: int = 180,
    padding: float = 0.08,
) -> dict[str, tuple[float, float]]:
    if not positions:
        return positions

    adjusted = {
        author: [coords[0], coords[1]]
        for author, coords in positions.items()
    }
    authors = list(adjusted.keys())

    for _ in range(iterations):
        moved = False

        for index, author_a in enumerate(authors):
            x_a, y_a = adjusted[author_a]
            radius_a = node_radius_by_author.get(author_a, 0.2)

            for author_b in authors[index + 1:]:
                x_b, y_b = adjusted[author_b]
                radius_b = node_radius_by_author.get(author_b, 0.2)

                dx = x_b - x_a
                dy = y_b - y_a
                distance = math.hypot(dx, dy)
                minimum_distance = radius_a + radius_b + padding

                if distance >= minimum_distance:
                    continue

                moved = True
                if distance == 0:
                    dx = 0.01
                    dy = 0.0
                    distance = 0.01

                overlap = minimum_distance - distance
                push_x = (dx / distance) * overlap * 0.5
                push_y = (dy / distance) * overlap * 0.5

                adjusted[author_a][0] -= push_x
                adjusted[author_a][1] -= push_y
                adjusted[author_b][0] += push_x
                adjusted[author_b][1] += push_y

        if not moved:
            break

    return {
        author: (coords[0], coords[1])
        for author, coords in adjusted.items()
    }


def plot_collaboration_network(
    network_data: dict,
    authorship_payload: dict,
    output_path: Path,
    snapshot_label: str,
    layout_name: str = "spring",
) -> None:
    collaboration_network = authorship_payload.get("collaboration_network", {})
    raw_nodes = collaboration_network.get("nodes", []) or []
    raw_edges = collaboration_network.get("edges", []) or []
    if not raw_nodes or not raw_edges:
        raise ValueError("Collaboration network plot requires non-empty collaboration network data.")

    author_bip_map = build_author_bip_map(network_data)

    graph = nx.Graph()
    for node in raw_nodes:
        author = str(node.get("id"))
        authored_bips = author_bip_map.get(author, [])
        graph.add_node(
            author,
            collaborator_degree=int(node.get("degree", 0) or 0),
            bip_count=len(authored_bips),
        )

    for edge in raw_edges:
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        weight = int(edge.get("weight", 1) or 1)
        graph.add_edge(source, target, weight=weight)

    components = sorted(nx.connected_components(graph), key=len, reverse=True)
    cluster_by_author = {}
    for cluster_index, members in enumerate(components):
        for author in members:
            cluster_by_author[author] = cluster_index

    top_authors = sorted(
        graph.nodes(),
        key=lambda author: (-graph.nodes[author].get("bip_count", 0), author),
    )[:10]
    top_author_set = set(top_authors)

    authored_counts = [max(1, int(graph.nodes[author].get("bip_count", 0))) for author in graph.nodes()]
    node_sizes = [90 + (count**0.95) * 58 for count in authored_counts]
    node_radius_by_author = {}
    for author, node_size in zip(graph.nodes(), node_sizes):
        radius = 0.2 + math.sqrt(node_size) / 18
        if author in top_author_set:
            radius += min(2.0, 0.018 * len(author) + 0.35)
        else:
            radius += 0.08
        node_radius_by_author[author] = radius

    positions = _build_layout(graph, layout_name)
    positions = _resolve_node_overlaps(positions, node_radius_by_author, iterations=260, padding=0.24)
    positions = _resolve_node_overlaps(positions, node_radius_by_author, iterations=200, padding=0.32)
    edge_widths = [0.65 + float(data.get("weight", 1)) * 0.65 for _, _, data in graph.edges(data=True)]
    cluster_colors = {
        author: CLUSTER_COLORS[cluster_by_author.get(author, 0) % len(CLUSTER_COLORS)]
        for author in graph.nodes()
    }
    node_facecolors = [with_plot_alpha(cluster_colors[author], PLOT_COLOR_ALPHA) for author in graph.nodes()]
    node_edgecolors = [with_plot_alpha(cluster_colors[author], PLOT_COLOR_ALPHA) for author in graph.nodes()]
    edge_colors = [cluster_colors[source] for source, _, _ in graph.edges(data=True)]

    figure, axis = plt.subplots(figsize=(11, 6.5))
    nx.draw_networkx_edges(
        graph,
        positions,
        ax=axis,
        width=edge_widths,
        edge_color=edge_colors,
        alpha=0.42,
        arrows=True,
        arrowstyle="-",
        connectionstyle="arc3,rad=0.11",
    )
    nx.draw_networkx_nodes(
        graph,
        positions,
        ax=axis,
        node_size=node_sizes,
        node_color=node_facecolors,
        edgecolors=node_edgecolors,
        linewidths=1.1,
    )

    for author, (x, y) in positions.items():
        bip_count = int(graph.nodes[author].get("bip_count", 0))
        if author in top_author_set:
            label = f"{author} ({bip_count})"
            font_size = 9.5
        else:
            label = str(bip_count)
            font_size = 5.8

        axis.text(
            x,
            y,
            label,
            ha="center",
            va="center",
            fontsize=font_size,
            color="#111111",
            zorder=5,
        )

    axis.set_title(f"Collaboration Network ({snapshot_label}, {layout_name})")
    axis.axis("off")
    figure.tight_layout()
    save_figure(figure, output_path)


def render_collaboration_network_layout_suite(
    network_data: dict,
    authorship_payload: dict,
    output_dir: Path,
    filename_prefix: str,
    snapshot_label: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for layout_name in COLLABORATION_LAYOUTS:
        plot_collaboration_network(
            network_data=network_data,
            authorship_payload=authorship_payload,
            output_path=output_dir / f"{filename_prefix}_collaboration_network_{layout_name}.pdf",
            snapshot_label=snapshot_label,
            layout_name=layout_name,
        )
