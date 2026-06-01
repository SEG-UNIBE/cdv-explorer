import hashlib
import math
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.legend_handler import HandlerBase
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch

from analysis.dependencies.constants import (
    BODY_EXTRACTED_LLM,
    BODY_EXTRACTED_REGEX,
    LEGACY_APPROACH_ALIASES,
    PREAMBLE_DEPENDENCY_SUBTYPES,
    PREAMBLE_EXTRACTED,
)
from paper.plot_colors import PLOT_COLOR_ALPHA, with_plot_alpha

try:
    from networkx.drawing.nx_agraph import graphviz_layout
    import pygraphviz  # noqa: F401

    graphviz_available = True
except ImportError:
    graphviz_available = False

DEFAULT_BIPS_OF_INTEREST = [
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

DEFAULT_BIPS_TO_EXCLUDE = [
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

LEGEND_ARROW_STYLE = "-|>"
LEGEND_ARROW_SCALE = 5
LEGEND_ARROWHEAD_MARKER_SIZE = 4


class SolidArrowHeadLegendHandler(HandlerBase):
    def create_artists(self, legend, orig_handle, xdescent, ydescent, width, height, fontsize, trans):
        color = orig_handle.get_edgecolor()
        x_start = xdescent + width * 0.05
        x_end = xdescent + width * 0.68
        x_head = xdescent + width * 0.82
        y_mid = ydescent + height / 2

        shaft = Line2D(
            [x_start, x_end],
            [y_mid, y_mid],
            linestyle=orig_handle.get_linestyle(),
            linewidth=orig_handle.get_linewidth(),
            color=color,
            solid_capstyle="butt",
        )
        head = Line2D(
            [x_head],
            [y_mid],
            linestyle="None",
            marker=">",
            markersize=LEGEND_ARROWHEAD_MARKER_SIZE,
            markerfacecolor=color,
            markeredgecolor=color,
        )

        shaft.set_transform(trans)
        head.set_transform(trans)
        return [shaft, head]


ARROW_LEGEND_HANDLER_MAP = {FancyArrowPatch: SolidArrowHeadLegendHandler()}


def build_arrow_legend_handle(*, color, linestyle, linewidth, label):
    handle = FancyArrowPatch(
        (0, 0),
        (1, 0),
        arrowstyle=LEGEND_ARROW_STYLE,
        mutation_scale=LEGEND_ARROW_SCALE,
        linewidth=linewidth,
        linestyle=linestyle,
        color=color,
    )
    handle.set_label(label)
    return handle


def _slugify(parts) -> str:
    return "-".join(str(part).replace("_", "-") for part in parts)


def get_links_by_type(network_links, link_type):
    explicit = network_links.get(PREAMBLE_EXTRACTED, {}) or network_links.get(LEGACY_APPROACH_ALIASES[PREAMBLE_EXTRACTED], {})
    if link_type in PREAMBLE_DEPENDENCY_SUBTYPES:
        return explicit.get(link_type, [])
    if link_type == PREAMBLE_EXTRACTED:
        seen = set()
        merged = []
        for subtype in PREAMBLE_DEPENDENCY_SUBTYPES:
            for link in explicit.get(subtype, []):
                key = (link.get("source"), link.get("target"))
                if key in seen:
                    continue
                seen.add(key)
                merged.append(link)
        return merged
    return network_links.get(link_type, network_links.get(LEGACY_APPROACH_ALIASES.get(link_type, ""), []))


def iter_all_links(network_links):
    for link_type, links in network_links.items():
        if link_type in {PREAMBLE_EXTRACTED, LEGACY_APPROACH_ALIASES[PREAMBLE_EXTRACTED]} and isinstance(links, dict):
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


def compute_layout_positions(graph: nx.DiGraph, layout_name: str) -> dict:
    layout_configs = {
        "spring_default": {"algo": "spring", "params": {"k": 0.3, "iterations": 100, "seed": 41}},
        "spring_spread": {"algo": "spring", "params": {"k": 3, "iterations": 200, "seed": 41}},
        "spring_scaled": {"algo": "spring_scaled", "params": {"iterations": 200, "seed": 41}},
        "planar": {"algo": "planar", "params": {}},
        "spectral": {"algo": "spectral", "params": {"scale": 1.45}},
        "shell": {"algo": "shell", "params": {"scale": 1.2}},
        "circular": {"algo": "circular", "params": {"scale": 1.2}},
        "bipartite": {"algo": "bipartite", "params": {"scale": 1.25, "align": "vertical"}},
        "multipartite": {"algo": "multipartite", "params": {"scale": 1.25, "align": "vertical", "subset_key": "subset"}},
        "kamada_kawai": {"algo": "kamada_kawai", "params": {"scale": 0.8}},
    }

    if graphviz_available:
        layout_configs.update(
            {
                "graphviz_dot": {"algo": "graphviz", "prog": "dot"},
                "graphviz_neato": {"algo": "graphviz", "prog": "neato"},
                "graphviz_fdp": {"algo": "graphviz", "prog": "fdp"},
            }
        )

    if layout_name not in layout_configs:
        raise ValueError(f"Unsupported layout name: {layout_name}")

    config = layout_configs[layout_name]
    if config["algo"] == "spring":
        return nx.spring_layout(graph, **config["params"])
    if config["algo"] == "spring_scaled":
        node_count = max(graph.order(), 1)
        return nx.spring_layout(graph, k=5 / math.sqrt(node_count), **config["params"])
    if config["algo"] == "planar":
        return nx.planar_layout(graph.to_undirected(), **config["params"])
    if config["algo"] == "spectral":
        pos = nx.spectral_layout(graph.to_undirected(), **config["params"])
        resolve_near_overlaps(pos, threshold=0.1)
        return pos
    if config["algo"] == "shell":
        ordered_nodes = sorted(graph.nodes(), key=lambda node_id: (-graph.degree(node_id), int(node_id)))
        inner_count = max(1, math.ceil(len(ordered_nodes) / 3))
        shells = [ordered_nodes[:inner_count], ordered_nodes[inner_count:]]
        shells = [shell for shell in shells if shell]
        pos = nx.shell_layout(graph.to_undirected(), nlist=shells, **config["params"])
        resolve_near_overlaps(pos, threshold=0.09)
        return pos
    if config["algo"] == "circular":
        pos = nx.circular_layout(graph.to_undirected(), **config["params"])
        resolve_near_overlaps(pos, threshold=0.08)
        return pos
    if config["algo"] == "bipartite":
        left_nodes = sorted(
            [node_id for node_id in graph.nodes() if graph.out_degree(node_id) >= graph.in_degree(node_id)],
            key=int,
        )
        if not left_nodes or len(left_nodes) == graph.number_of_nodes():
            ordered_nodes = sorted(graph.nodes(), key=int)
            midpoint = max(1, math.ceil(len(ordered_nodes) / 2))
            left_nodes = ordered_nodes[:midpoint]
        pos = nx.bipartite_layout(graph.to_undirected(), left_nodes, **config["params"])
        resolve_near_overlaps(pos, threshold=0.08)
        return pos
    if config["algo"] == "multipartite":
        pos = nx.multipartite_layout(graph, **config["params"])
        resolve_near_overlaps(pos, threshold=0.08)
        return pos
    if config["algo"] == "kamada_kawai":
        pos = nx.kamada_kawai_layout(graph, **config["params"])
        resolve_near_overlaps(pos, threshold=0.1)
        for node_id, dx, dy in [(142, 0.049, -0.58), (173, -0.04, -0.14), (83, 0.05, 0.08), (146, 0, 0.12)]:
            if node_id in pos:
                relocate_manually(pos, node_id=node_id, relative_x=dx, relative_y=dy)
        return pos
    if config["algo"] == "graphviz":
        return graphviz_layout(graph, prog=config["prog"])
    raise ValueError(f"Unsupported layout algorithm: {config['algo']}")


def draw_static_network_with_layouts(
    network_data,
    output_dir: Path,
    link_type=None,
    color_by="group",
    bips_to_show=None,
    bips_to_exclude=None,
    full_title="Plot",
    edge_type_styles=None,
    filename_prefix: str | None = None,
    filename_stem: str | None = None,
):
    output_dir.mkdir(parents=True, exist_ok=True)

    if link_type is None:
        link_type = [BODY_EXTRACTED_REGEX]

    if edge_type_styles is None:
        edge_type_styles = {
            BODY_EXTRACTED_LLM: {
                "color": "gray",
                "style": "solid",
                "alpha": 0.6,
                "label": "implicit dependencies (LLM)",
            },
            BODY_EXTRACTED_REGEX: {
                "color": "black",
                "style": "dashed",
                "alpha": 0.6,
                "label": "explicit references (regex)",
            },
            "requires": {"color": "red", "style": "solid", "alpha": PLOT_COLOR_ALPHA, "label": "requires"},
            "replaces": {"color": "blue", "style": "solid", "alpha": PLOT_COLOR_ALPHA, "label": "replaces"},
            "proposed_replacement": {
                "color": "green",
                "style": "solid",
                "alpha": PLOT_COLOR_ALPHA,
                "label": "proposed-replacement",
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

    node_colors_data = []
    cmap_for_plot = None
    vmin_for_plot = None
    vmax_for_plot = None
    legend_handles = []
    group_to_index_map = {}

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
                plt.Line2D(
                    [],
                    [],
                    marker="o",
                    color="w",
                    label=label_with_count,
                    markerfacecolor=with_plot_alpha(color_for_legend),
                    markersize=10,
                )
            )
    elif color_by == "compliance_score":
        compliance_scores = nx.get_node_attributes(graph, "compliance_score")
        node_colors_data = [compliance_scores[node] for node in graph.nodes()]
        cmap_for_plot = plt.get_cmap("viridis")
        vmin_for_plot = min(node_colors_data) if node_colors_data else 0
        vmax_for_plot = max(node_colors_data) if node_colors_data else 1
    else:
        node_colors_data = ["grey"] * len(graph.nodes())

    layout_names = ["spring_default", "spring_spread", "kamada_kawai"]
    if graphviz_available:
        layout_names.extend(["graphviz_dot", "graphviz_neato", "graphviz_fdp"])

    for layout_name in layout_names:
        try:
            pos = compute_layout_positions(graph, layout_name)
        except (ImportError, nx.NetworkXException, RuntimeError, ValueError, TypeError):
            continue

        plt.figure(figsize=(10, 6))
        nodes_plot = nx.draw_networkx_nodes(
            graph,
            pos,
            node_size=350,
            node_color=node_colors_data,
            cmap=cmap_for_plot,
            alpha=PLOT_COLOR_ALPHA,
            vmin=vmin_for_plot,
            vmax=vmax_for_plot,
            edgecolors="black",
            linewidths=0.9,
        )

        for lt in link_type:
            style_info = edge_type_styles.get(lt, {})
            color = style_info.get("color", "black")
            linestyle = style_info.get("style", "solid")
            alpha = style_info.get("alpha", PLOT_COLOR_ALPHA)
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
            plt.text(x, y, label, fontsize=7, fontweight="bold", family="monospace", ha="center", va="center")

        plt.title(full_title, pad=25, y=1.0)

        edge_legend_handles = []
        for lt in link_type:
            style_info = edge_type_styles.get(lt, {})
            if style_info.get("alpha", PLOT_COLOR_ALPHA) == 0.0:
                continue
            color = "gray" if style_info.get("color", "black") == "outgoing-color" else style_info.get("color", "black")
            linestyle = style_info.get("style", "solid")
            base_label = style_info.get("label", lt)
            edge_count = len(edges_by_type.get(lt, []))
            label_with_count = f"{base_label} $(n={edge_count})$"
            legend_color = with_plot_alpha(color, style_info.get("alpha", PLOT_COLOR_ALPHA))
            edge_legend_handles.append(
                build_arrow_legend_handle(
                    color=legend_color,
                    linestyle=linestyle,
                    linewidth=1.2,
                    label=label_with_count,
                )
            )

        all_legend_handles = legend_handles + edge_legend_handles
        if all_legend_handles:
            ncol = math.ceil(len(all_legend_handles) / 2)
            plt.legend(
                handles=all_legend_handles,
                loc="lower center",
                bbox_to_anchor=(0.5, 0.95),
                ncol=ncol,
                handler_map=ARROW_LEGEND_HANDLER_MAP,
                frameon=False,
                fancybox=False,
                shadow=False,
                fontsize=8.5,
                handlelength=1.8,
                columnspacing=1.0,
                handletextpad=0.35,
                labelspacing=0.6,
            )
        elif color_by == "compliance_score" and nodes_plot:
            cbar = plt.colorbar(nodes_plot, ax=plt.gca(), orientation="vertical", pad=0.02)
            cbar.set_label("Compliance Score")

        plt.axis("off")
        plt.tight_layout(rect=[0, 0, 1, 0.99])

        base_stem = filename_stem or _slugify([graph.number_of_nodes(), *link_type, color_by])
        if base_stem.startswith("dependency_"):
            stem = f"dep_{layout_name}_{base_stem[len('dependency_'):]}"
        else:
            stem = f"dep_{layout_name}_{base_stem}"
        prefix = f"{filename_prefix}_" if filename_prefix else ""
        output_path = output_dir / f"{prefix}{stem}.pdf"
        plt.savefig(output_path, format="pdf")
        plt.close()


def render_default_dependency_plot_suite(network_data, output_dir: Path, filename_prefix: str | None = None) -> None:
    plot_specs = [
        {
            "filename_stem": "dependency_body_extracted_regex_focus",
            "link_type": [BODY_EXTRACTED_REGEX, "requires", "replaces", "proposed_replacement"],
            "color_by": "group",
            "bips_to_show": DEFAULT_BIPS_OF_INTEREST,
            "bips_to_exclude": DEFAULT_BIPS_TO_EXCLUDE,
            "full_title": "Selected proposals with explicit references (regex extraction)",
            "edge_type_styles": {
                BODY_EXTRACTED_REGEX: {
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
                "proposed_replacement": {
                    "color": "green",
                    "style": "solid",
                    "alpha": 0.0,
                    "label": "proposed replacement",
                },
            },
        },
        {
            "filename_stem": "dependency_explicit_fields_focus",
            "link_type": ["requires", "replaces", "proposed_replacement", BODY_EXTRACTED_REGEX],
            "color_by": "group",
            "bips_to_show": DEFAULT_BIPS_OF_INTEREST,
            "bips_to_exclude": DEFAULT_BIPS_TO_EXCLUDE,
            "full_title": "Selected proposals with explicit dependencies (preamble fields)",
            "edge_type_styles": {
                BODY_EXTRACTED_REGEX: {
                    "color": "black",
                    "style": "solid",
                    "alpha": 0.0,
                    "label": "explicit references (regex)",
                },
                "requires": {
                    "color": "red",
                    "style": "solid",
                    "alpha": PLOT_COLOR_ALPHA,
                    "label": "requires",
                },
                "replaces": {
                    "color": "blue",
                    "style": "solid",
                    "alpha": PLOT_COLOR_ALPHA,
                    "label": "replaces",
                },
                "proposed_replacement": {
                    "color": "green",
                    "style": "solid",
                    "alpha": PLOT_COLOR_ALPHA,
                    "label": "proposed replacement",
                },
            },
        },
        {
            "filename_stem": "dependency_implicit_focus",
            "link_type": [BODY_EXTRACTED_LLM],
            "color_by": "group",
            "bips_to_show": None,
            "bips_to_exclude": None,
            "full_title": "Selected proposals with implicit dependencies (LLM extraction)",
            "edge_type_styles": {
                BODY_EXTRACTED_LLM: {
                    "color": "gray",
                    "style": "solid",
                    "alpha": PLOT_COLOR_ALPHA,
                    "label": "implicit dependencies (LLM)",
                }
            },
        },
        {
            "filename_stem": "dependency_full_network",
            "link_type": [BODY_EXTRACTED_REGEX, "requires", "replaces", "proposed_replacement", BODY_EXTRACTED_LLM],
            "color_by": "group",
            "bips_to_show": None,
            "bips_to_exclude": None,
            "full_title": "Selected proposals: explicit references, explicit dependencies, and implicit dependencies",
            "edge_type_styles": None,
        },
    ]

    for plot_spec in plot_specs:
        draw_static_network_with_layouts(
            network_data,
            output_dir=output_dir,
            filename_prefix=filename_prefix,
            **plot_spec,
        )
