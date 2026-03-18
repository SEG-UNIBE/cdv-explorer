import argparse
import hashlib
import math
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D

from ecosystem_config import ACTIVE_ECOSYSTEM
from analysis.artifact_io import load_network_data

try:
    from networkx.drawing.nx_agraph import graphviz_layout

    graphviz_available = True
except ImportError:
    graphviz_available = False


def get_links_by_type(network_links, link_type):
    explicit = network_links.get("explicit_dependencies", {})
    if link_type in {"requires", "replaces", "superseded_by"}:
        return explicit.get(link_type, [])
    if link_type == "explicit_dependencies":
        seen = set()
        merged = []
        for subtype in ("requires", "replaces", "superseded_by"):
            for link in explicit.get(subtype, []):
                key = (link.get("source"), link.get("target"))
                if key in seen:
                    continue
                seen.add(key)
                merged.append(link)
        return merged
    return network_links.get(link_type, [])


def iter_all_links(network_links):
    for link_type, links in network_links.items():
        if link_type == "explicit_dependencies" and isinstance(links, dict):
            for subtype_links in links.values():
                for link in subtype_links:
                    yield link
            continue
        for link in links:
            yield link


def resolve_near_overlaps(pos, threshold=0.02, max_iterations=10):
    def pair_seed(a, b):
        key = f"{min(a, b)}-{max(a, b)}"
        digest = hashlib.sha256(key.encode()).hexdigest()
        return int(digest[:8], 16)

    for _ in range(max_iterations):
        nodes = list(pos.keys())
        made_adjustments = False

        for i, node1 in enumerate(nodes):
            for j in range(i + 1, len(nodes)):
                node2 = nodes[j]
                x1, y1 = pos[node1]
                x2, y2 = pos[node2]
                dist = np.hypot(x2 - x1, y2 - y1)

                if dist < threshold:
                    seed = pair_seed(node1, node2)
                    rng = np.random.default_rng(seed)
                    angle = rng.uniform(0, 2 * np.pi)
                    offset = threshold * np.array([np.cos(angle), np.sin(angle)])

                    pos[node1] = (x1 - offset[0] / 2, y1 - offset[1] / 2)
                    pos[node2] = (x2 + offset[0] / 2, y2 + offset[1] / 2)
                    made_adjustments = True

        if not made_adjustments:
            break


def relocate_manually(pos, node_id, relative_x=0.0, relative_y=0.0):
    if node_id in pos:
        current_x, current_y = pos[node_id]
        pos[node_id] = (current_x + relative_x, current_y + relative_y)
    else:
        raise KeyError(f"Node ID {node_id} not found in position dictionary.")


def draw_static_network_with_layouts(
    network_data,
    output_dir: Path,
    link_type=None,
    color_by="group",
    bips_to_show=None,
    bips_to_exclude=None,
    full_title="Plot",
    edge_type_styles=None,
):
    output_dir.mkdir(parents=True, exist_ok=True)

    if link_type is None:
        link_type = ["explicit_references"]

    if edge_type_styles is None:
        edge_type_styles = {
            "implicit_dependencies": {
                "color": "gray",
                "style": "solid",
                "alpha": 0.6,
                "label": "implicit dependencies (LLM)",
            },
            "explicit_references": {
                "color": "black",
                "style": "dashed",
                "alpha": 0.6,
                "label": "explicit references (regex)",
            },
            "requires": {"color": "red", "style": "solid", "alpha": 1.0, "label": "requires"},
            "replaces": {"color": "blue", "style": "solid", "alpha": 1.0, "label": "replaces"},
            "superseded_by": {
                "color": "green",
                "style": "solid",
                "alpha": 1.0,
                "label": "superseded by",
            },
        }

    nodes_to_display_set = None
    if bips_to_show is not None:
        core_bips_set = set(bips_to_show)
        nodes_to_display_set = set(core_bips_set)
        for link_data in iter_all_links(network_data["links"]):
            source_id = int(link_data["source"])
            target_id = int(link_data["target"])
            if source_id in core_bips_set:
                nodes_to_display_set.add(target_id)
            if target_id in core_bips_set:
                nodes_to_display_set.add(source_id)

    if bips_to_exclude is not None and nodes_to_display_set is not None:
        nodes_to_display_set = nodes_to_display_set - set(bips_to_exclude)

    graph = nx.DiGraph()

    for node_data in network_data["nodes"]:
        node_id = int(node_data["id"])
        if nodes_to_display_set is None or node_id in nodes_to_display_set:
            original_status = node_data.get("status", "(not specified)")
            processed_status = original_status.split(" ")[0].strip()
            graph.add_node(
                node_id,
                group=processed_status,
                compliance_score=node_data.get("compliance_score", 0),
            )

    edges_by_type = {lt: [] for lt in link_type}
    for lt in link_type:
        for link_data in get_links_by_type(network_data["links"], lt):
            source_id = int(link_data["source"])
            target_id = int(link_data["target"])
            if graph.has_node(source_id) and graph.has_node(target_id):
                graph.add_edge(source_id, target_id)
                edges_by_type[lt].append((source_id, target_id))

    group_attr = nx.get_node_attributes(graph, "group")
    group_counts = Counter(group_attr.values())
    sorted_groups = sorted(group_counts.items(), key=lambda item: item[1], reverse=True)
    sorted_group_names = [group for group, _ in sorted_groups]

    node_colors_data = []
    cmap_for_plot = None
    vmin_for_plot = None
    vmax_for_plot = None
    legend_handles = []

    if color_by == "group":
        default_colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
        sorted_group_names = sorted(set(group_attr.values()))
        group_to_index_map = {group: i for i, group in enumerate(sorted_group_names)}

        if len(sorted_group_names) > len(default_colors):
            extended_colors = [default_colors[i % len(default_colors)] for i in range(len(sorted_group_names))]
            cmap_for_plot = ListedColormap(extended_colors)
        else:
            cmap_for_plot = ListedColormap(default_colors[: len(sorted_group_names)])

        vmin_for_plot = 0
        vmax_for_plot = len(sorted_group_names) - 1
        node_colors_data = [group_to_index_map[group_attr[n]] for n in graph.nodes()]

        for i, group in enumerate(sorted_group_names):
            count = group_counts[group]
            label_with_count = f"{group} $(n={count})$"
            color_for_legend = cmap_for_plot(i / (len(sorted_group_names) - 1) if len(sorted_group_names) > 1 else 0.5)
            legend_handles.append(
                plt.Line2D([], [], marker="o", color="w", label=label_with_count, markerfacecolor=color_for_legend, markersize=10)
            )
    elif color_by == "compliance_score":
        compliance_scores = nx.get_node_attributes(graph, "compliance_score")
        node_colors_data = [compliance_scores[node] for node in graph.nodes()]
        cmap_for_plot = plt.get_cmap("viridis")
        vmin_for_plot = min(node_colors_data) if node_colors_data else 0
        vmax_for_plot = max(node_colors_data) if node_colors_data else 1
    else:
        node_colors_data = ["grey"] * len(graph.nodes())

    layout_configs = [
        {"name": "spring_default", "algo": "spring", "params": {"k": 0.3, "iterations": 100, "seed": 41}},
        {"name": "spring_spread", "algo": "spring", "params": {"k": 3, "iterations": 200, "seed": 41}},
        {"name": "kamada_kawai", "algo": "kamada_kawai", "params": {"scale": 0.8}},
    ]

    if graphviz_available:
        layout_configs.extend(
            [
                {"name": "graphviz_dot", "algo": "graphviz", "prog": "dot"},
                {"name": "graphviz_neato", "algo": "graphviz", "prog": "neato"},
                {"name": "graphviz_fdp", "algo": "graphviz", "prog": "fdp"},
            ]
        )

    for config in layout_configs:
        layout_name = config["name"]
        pos = None

        try:
            if config["algo"] == "spring":
                pos = nx.spring_layout(graph, **config["params"])
            elif config["algo"] == "kamada_kawai":
                pos = nx.kamada_kawai_layout(graph, **config["params"])
                resolve_near_overlaps(pos, threshold=0.1)
                for node_id, dx, dy in [(142, 0.049, -0.58), (173, -0.04, -0.14), (83, 0.05, 0.08), (146, 0, 0.12)]:
                    if node_id in pos:
                        relocate_manually(pos, node_id=node_id, relative_x=dx, relative_y=dy)
            elif config["algo"] == "graphviz":
                pos = graphviz_layout(graph, prog=config["prog"])
            else:
                continue
        except (nx.NetworkXException, RuntimeError, ValueError, TypeError) as error:
            continue

        plt.figure(figsize=(10, 6))
        nodes_plot = nx.draw_networkx_nodes(
            graph,
            pos,
            node_size=350,
            node_color=node_colors_data,
            cmap=cmap_for_plot,
            alpha=0.85,
            vmin=vmin_for_plot,
            vmax=vmax_for_plot,
            edgecolors="black",
            linewidths=0.9,
        )

        for lt in link_type:
            style_info = edge_type_styles.get(lt, {})
            color = style_info.get("color", "black")
            linestyle = style_info.get("style", "solid")
            alpha = style_info.get("alpha", 1.0)
            edgelist = edges_by_type[lt]

            if color == "outgoing-color":
                edge_color_indices = []
                for src, _ in edgelist:
                    group = group_attr.get(src, "(not specified)")
                    group_index = group_to_index_map.get(group, 0)
                    edge_color_indices.append(group_index)
                edge_colors = [cmap_for_plot(i) for i in edge_color_indices]
            else:
                edge_colors = color

            nx.draw_networkx_edges(
                graph,
                pos,
                edgelist=edgelist,
                edge_color=edge_colors,
                style=linestyle,
                width=1.2,
                alpha=alpha,
                arrows=True,
                arrowstyle="-|>",
                connectionstyle="arc3,rad=0.2",
                min_source_margin=10,
                min_target_margin=10,
            )

        for node, (x, y) in pos.items():
            label = f"{node}"
            url = f"https://bips.dev/{node}"
            plt.text(x, y, label, fontsize=7, fontweight="bold", family="monospace", ha="center", va="center", url=url)

        plt.title(full_title, pad=25, y=1.0)

        edge_legend_handles = []
        for lt in link_type:
            style_info = edge_type_styles.get(lt, {})
            if style_info.get("alpha", 1.0) == 0.0:
                continue
            color = "gray" if style_info.get("color", "black") == "outgoing-color" else style_info.get("color", "black")
            linestyle = style_info.get("style", "solid")
            base_label = style_info.get("label", lt)
            edge_count = len(edges_by_type.get(lt, []))
            label_with_count = f"{base_label} $(n={edge_count})$"
            edge_legend_handles.append(Line2D([1], [0], color=color, linestyle=linestyle, linewidth=1.2, label=label_with_count))

        all_legend_handles = legend_handles + edge_legend_handles
        if all_legend_handles:
            ncol = math.ceil(len(all_legend_handles) / 2)
            plt.legend(
                handles=all_legend_handles,
                loc="lower center",
                bbox_to_anchor=(0.5, 0.95),
                ncol=ncol,
                fancybox=True,
                shadow=True,
                fontsize=8.5,
                columnspacing=1.0,
                handletextpad=0.2,
                labelspacing=0.6,
            )
        elif color_by == "compliance_score" and nodes_plot:
            cbar = plt.colorbar(nodes_plot, ax=plt.gca(), orientation="vertical", pad=0.02)
            cbar.set_label("Compliance Score")

        plt.axis("off")
        plt.tight_layout(rect=[0, 0, 1, 0.99])

        filename = f"network_{graph.number_of_nodes()}_{link_type}_{color_by}_{layout_name}.pdf"
        output_path = output_dir / filename
        plt.savefig(output_path, format="pdf")
        plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Render dependency network plots.")
    parser.add_argument("--snapshot", help="Load a specific snapshot artifact by date (YYYY-MM-DD).")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory where generated PDF plots are written.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    snapshot_label = args.snapshot or "latest"
    output_dir = repo_root / (
        args.output_dir
        or f"{ACTIVE_ECOSYSTEM['postprocess']}/{snapshot_label}/dependencies/plots"
    )

    data = load_network_data(snapshot=args.snapshot)

    my_bips_of_interest = [
        9,
        20,
        21,
        32,
        37,
        60,
        74,
        84,
        118,
        141,
        142,
        151,
        173,
        174,
        324,
        342,
        350,
        352,
        370,
        372,
        374,
        375,
    ]

    my_bips_to_exclude = [
        13,
        16,
        30,
        34,
        38,
        39,
        47,
        50,
        65,
        66,
        68,
        70,
        78,
        80,
        81,
        132,
        144,
        150,
        151,
        324,
        353,
        85,
        91,
        72,
        347,
        113,
        152,
        300,
        330,
        124,
        109,
        8,
        371,
        75,
        152,
        380,
        90,
        339,
        49,
        86,
        45,
        48,
        46,
        329,
        390,
        157,
        60,
        117,
        116,
        136,
        119,
        31,
        37,
        74,
        112,
        141,
        143,
        145,
        147,
        43,
        44,
        87,
        158,
        114,
        320,
        351,
        121,
        149,
        115,
        111,
        120,
        127,
        175,
        388,
        325,
        88,
        148,
        93,
        62,
    ]

    edge_type_styles = {
        "explicit_references": {
            "color": "outgoing-color",
            "style": "dashed",
            "alpha": 0.8,
            "label": "explicit references (regex)",
        },
        "requires": {
            "color": "red",
            "style": "solid",
            "alpha": 0.0,
            "label": "requires",
        },
        "replaces": {
            "color": "blue",
            "style": "solid",
            "alpha": 0.0,
            "label": "replaces",
        },
        "superseded_by": {
            "color": "green",
            "style": "solid",
            "alpha": 0.0,
            "label": "superseded by",
        },
    }

    draw_static_network_with_layouts(
        data,
        output_dir=output_dir,
        link_type=["explicit_references", "requires", "replaces", "superseded_by"],
        color_by="group",
        bips_to_show=my_bips_of_interest,
        bips_to_exclude=my_bips_to_exclude,
        full_title="Selected proposals with explicit references (regex extraction)",
        edge_type_styles=edge_type_styles,
    )

    edge_type_styles = {
        "explicit_references": {
            "color": "black",
            "style": "solid",
            "alpha": 0.0,
            "label": "explicit references (regex)",
        },
        "requires": {
            "color": "red",
            "style": "solid",
            "alpha": 1.0,
            "label": "requires",
        },
        "replaces": {
            "color": "blue",
            "style": "solid",
            "alpha": 1.0,
            "label": "replaces",
        },
        "superseded_by": {
            "color": "green",
            "style": "solid",
            "alpha": 1.0,
            "label": "superseded by",
        },
    }

    draw_static_network_with_layouts(
        data,
        output_dir=output_dir,
        link_type=["requires", "replaces", "superseded_by", "explicit_references"],
        color_by="group",
        bips_to_show=my_bips_of_interest,
        bips_to_exclude=my_bips_to_exclude,
        full_title="Selected proposals with explicit dependencies (preamble fields)",
        edge_type_styles=edge_type_styles,
    )

    edge_type_styles = {
        "implicit_dependencies": {
            "color": "gray",
            "style": "solid",
            "alpha": 1.0,
            "label": "implicit dependencies (LLM)",
        }
    }

    draw_static_network_with_layouts(
        data,
        output_dir=output_dir,
        link_type=["implicit_dependencies"],
        color_by="group",
        bips_to_show=None,
        bips_to_exclude=None,
        full_title="Selected proposals with implicit dependencies (LLM extraction)",
        edge_type_styles=edge_type_styles,
    )

    draw_static_network_with_layouts(
        data,
        output_dir=output_dir,
        link_type=["explicit_references", "requires", "replaces", "superseded_by", "implicit_dependencies"],
        color_by="group",
        bips_to_show=None,
        bips_to_exclude=None,
        full_title="Selected proposals: explicit references, explicit dependencies, and implicit dependencies",
        edge_type_styles=None,
    )


if __name__ == "__main__":
    main()
