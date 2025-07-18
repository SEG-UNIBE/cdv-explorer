import hashlib
import math
import pickle
import networkx as nx
import matplotlib.pyplot as plt
from collections import Counter
import matplotlib.cm as cm
import scipy
import numpy as np
from matplotlib.colors import ListedColormap # Import ListedColormap
from matplotlib.lines import Line2D

# --- Graphviz / PyGraphviz setup ---
# Make sure you have pygraphviz installed: pip install pygraphviz
try:
    import pygraphviz
    from networkx.drawing.nx_agraph import graphviz_layout
    graphviz_available = True
    print("PyGraphviz detected. Graphviz layouts will be attempted.")
except ImportError:
    graphviz_available = False
    print("PyGraphviz not found. Graphviz layouts (dot, neato, fdp) will be skipped.")
# --- End Graphviz setup ---

def resolve_near_overlaps(pos, threshold=0.02, max_iterations=10):
    def pair_seed(a, b):
        # Create a deterministic seed from the pair of node IDs
        key = f"{min(a, b)}-{max(a, b)}"
        digest = hashlib.sha256(key.encode()).hexdigest()
        return int(digest[:8], 16)  # use first 8 hex chars

    for iteration in range(max_iterations):
        nodes = list(pos.keys())
        made_adjustments = False

        for i, node1 in enumerate(nodes):
            for j in range(i + 1, len(nodes)):
                node2 = nodes[j]
                x1, y1 = pos[node1]
                x2, y2 = pos[node2]
                dist = np.hypot(x2 - x1, y2 - y1)

                if dist < threshold:
                    # Deterministic offset using node pair
                    seed = pair_seed(node1, node2)
                    rng = np.random.default_rng(seed)
                    angle = rng.uniform(0, 2 * np.pi)
                    offset = threshold * np.array([np.cos(angle), np.sin(angle)])

                    pos[node1] = (x1 - offset[0] / 2, y1 - offset[1] / 2)
                    pos[node2] = (x2 + offset[0] / 2, y2 + offset[1] / 2)
                    made_adjustments = True

        if not made_adjustments:
            break  # Done!

def draw_static_network_with_layouts(network_data, link_type=['references'], color_by='group', bips_to_show=None,
                                     bips_to_exclude=None,
                                     full_title='Plot', edge_type_styles=None):

    # Define color and style for each link type
    if edge_type_styles is None:
        edge_type_styles = {
            'dependencies': {
                'color': 'gray', 'style': 'solid', 'alpha': 0.6,
                'label': 'LLM-detected reference'
            },
            'references': {
                'color': 'black', 'style': 'solid', 'alpha': 0.6,
                'label': 'regex reference'
            },
            'requires': {
                'color': 'red', 'style': 'solid', 'alpha': 1.0,
                'label': 'requires'
            },
            'replaces': {
                'color': 'blue', 'style': 'solid', 'alpha': 1.0,
                'label': 'replaces'
            },
            'superseded_by': {
                'color': 'green', 'style': 'solid', 'alpha': 1.0,
                'label': 'superseded'
            }
        }

    nodes_to_display_set = None
    if bips_to_show is not None:
        core_bips_set = set(bips_to_show)
        nodes_to_display_set = set(core_bips_set)
        for current_link_type_key in network_data['links']:
            for link_data in network_data['links'][current_link_type_key]:
                source_id = int(link_data['source'])
                target_id = int(link_data['target'])
                if source_id in core_bips_set:
                    nodes_to_display_set.add(target_id)
                if target_id in core_bips_set:
                    nodes_to_display_set.add(source_id)

    # Apply exclusions directly to the set
    if bips_to_exclude is not None:
        nodes_to_display_set = nodes_to_display_set - set(bips_to_exclude)


    G = nx.DiGraph()

    raw_status_counts = Counter()
    for node_data in network_data['nodes']:
        status = node_data.get('status', '(not specified)')
        raw_status_counts[status] += 1


    for node_data in network_data['nodes']:
        node_id = int(node_data['id'])
        if nodes_to_display_set is None or node_id in nodes_to_display_set:
            original_status = node_data.get('status', '(not specified)')
            processed_status = original_status.split(' ')[0].strip()
            G.add_node(
                node_id,
                group=processed_status,
                compliance_score=node_data.get('compliance_score', 0)
            )

    # Collect edges by type
    edges_by_type = {lt: [] for lt in link_type}
    for lt in link_type:
        for link_data in network_data['links'].get(lt, []):
            source_id = int(link_data['source'])
            target_id = int(link_data['target'])
            if G.has_node(source_id) and G.has_node(target_id):
                G.add_edge(source_id, target_id)
                edges_by_type[lt].append((source_id, target_id))


    group_attr = nx.get_node_attributes(G, 'group')
    group_counts = Counter(group_attr.values())
    sorted_groups = sorted(group_counts.items(), key=lambda item: item[1], reverse=True)
    sorted_group_names = [group for group, count in sorted_groups]

    node_colors_data = []
    cmap_for_plot = None
    vmin_for_plot = None
    vmax_for_plot = None
    legend_handles = []

    if color_by == 'group':
        default_colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
        group_to_index_map = {group: i for i, group in enumerate(sorted_group_names)}
        node_colors_data = [group_to_index_map[group_attr[node]] for node in G.nodes()]

        if len(sorted_group_names) > len(default_colors):
            extended_colors = [default_colors[i % len(default_colors)] for i in range(len(sorted_group_names))]
            cmap_for_plot = ListedColormap(extended_colors)
        else:
            cmap_for_plot = ListedColormap(default_colors[:len(sorted_group_names)])

        vmin_for_plot = 0
        vmax_for_plot = len(sorted_group_names) - 1

        for i, group in enumerate(sorted_group_names):
            count = group_counts[group]
            label_with_count = f"{group} $(n={count})$"
            color_for_legend = cmap_for_plot(i / (len(sorted_group_names) - 1) if len(sorted_group_names) > 1 else 0.5)
            legend_handles.append(
                plt.Line2D([], [], marker='o', color='w', label=label_with_count,
                           markerfacecolor=color_for_legend, markersize=10)
            )

    elif color_by == 'compliance_score':
        compliance_scores = nx.get_node_attributes(G, 'compliance_score')
        node_colors_data = [compliance_scores[node] for node in G.nodes()]
        cmap_for_plot = cm.viridis
        vmin_for_plot = min(node_colors_data) if node_colors_data else 0
        vmax_for_plot = max(node_colors_data) if node_colors_data else 1
    else:
        node_colors_data = ['grey'] * len(G.nodes())

    # --- Define different layout algorithms to try ---
    layout_configs = [
        {'name': 'spring_default', 'algo': 'spring', 'params': {'k': 0.3, 'iterations': 100, 'seed': 41}},
        {'name': 'spring_spread', 'algo': 'spring', 'params': {'k': 3, 'iterations': 200, 'seed': 41}},
        # {'name': 'spectral', 'algo': 'spectral', 'params': {}},
        {'name': 'kamada_kawai', 'algo': 'kamada_kawai', 'params': {'scale': 1}},
        # {'name': 'spiral', 'algo': 'spiral', 'params': {}},
        # {'name': 'random', 'algo': 'random', 'params': {}},
        # {'name': 'planar', 'algo': 'planar', 'params': {}},
        # {'name': 'shell', 'algo': 'shell', 'params': {}},
    ]

    if graphviz_available:
        layout_configs.extend([
            {'name': 'graphviz_dot', 'algo': 'graphviz', 'prog': 'dot'},     # Good for hierarchical/directed
            {'name': 'graphviz_neato', 'algo': 'graphviz', 'prog': 'neato'}, # Good for general force-directed
            {'name': 'graphviz_fdp', 'algo': 'graphviz', 'prog': 'fdp'},     # Good for larger force-directed
        ])

    # --- Loop through each layout configuration and create a plot ---
    for config in layout_configs:
        layout_name = config['name']
        print(f"Generating plot with layout: {layout_name}")
        pos = None

        try:
            if config['algo'] == 'spring':
                pos = nx.spring_layout(G, **config['params'])
            elif config['algo'] == 'kamada_kawai':
                pos = nx.kamada_kawai_layout(G, **config['params'])
                resolve_near_overlaps(pos, threshold=0.1)
            elif config['algo'] == 'shell':
                pos = nx.shell_layout(G, **config['params'])
            elif config['algo'] == 'spiral':
                pos = nx.spiral_layout(G, **config['params'])
            elif config['algo'] == 'planar':
                pos = nx.planar_layout(G, **config['params'])  # Requires G to be planar
            elif config['algo'] == 'random':
                pos = nx.random_layout(G, **config['params'])
            elif config['algo'] == 'spectral':
                pos = nx.spectral_layout(G, **config['params'])
            elif config['algo'] == 'circular':
                pos = nx.circular_layout(G, **config['params'])
            elif config['algo'] == 'graphviz':
                # For Graphviz, ensure G is converted to AGraph if necessary, though graphviz_layout handles it
                pos = graphviz_layout(G, prog=config['prog'])
            else:
                print(f"Unknown layout algorithm: {config['algo']}. Skipping.")
                continue # Skip this configuration

        except Exception as e:
            print(f"Failed to generate layout '{layout_name}': {e}. Skipping this layout.")
            continue # Skip this configuration if layout generation fails

        # Draw figure for the current layout
        plt.figure(figsize=(8, 12))
        nodes_plot = nx.draw_networkx_nodes(
            G, pos,
            node_size=350,
            node_color=node_colors_data,
            cmap=cmap_for_plot,
            alpha=0.85,
            vmin=vmin_for_plot,
            vmax=vmax_for_plot,
            edgecolors='black',
            linewidths=0.9
        )


        # Draw edges by type  # <<< modified
        for lt in link_type:
            style_info = edge_type_styles.get(lt, {})
            color = style_info.get('color', 'black')
            linestyle = style_info.get('style', 'solid')
            alpha = style_info.get('alpha', 1.0)
            nx.draw_networkx_edges(
                G, pos,
                edgelist=edges_by_type[lt],
                edge_color=color,
                style=linestyle,
                width=1.2,
                alpha=alpha,
                arrows=True,
                arrowstyle='-|>',
                connectionstyle='arc3,rad=0.2',  # <<< curve
                min_source_margin=10,
                min_target_margin=10
            )

        for node, (x, y) in pos.items():
            label = f"{node}"
            url = f"https://bips.dev/{node}"  # or your preferred format
            plt.text(
                x, y,                 # small vertical offset
                label,
                fontsize=7,
                fontweight='bold',
                family='monospace',
                ha='center',
                va='center',
                url=url                      # <<< makes the label clickable in PDF
            )

        plt.title(full_title, pad=10, y=1.0)

        # Combine node and edge legends
        edge_legend_handles = []
        for lt in link_type:
            style_info = edge_type_styles.get(lt, {})
            if style_info.get('alpha', 1.0) == 0.0:
                continue  # Skip legend entry for invisible edge type
            color = style_info.get('color', 'black')
            linestyle = style_info.get('style', 'solid')
            label = style_info.get('label', lt)  # <<< use custom label if provided
            base_label = style_info.get('label', lt)
            edge_count = len(edges_by_type.get(lt, []))
            label_with_count = f"{base_label} $(n={edge_count})$"

            arrow_line = Line2D(
                [1], [0],
                color=color,
                linestyle=linestyle,
                linewidth=1.2,
                # marker='>',
                # markersize=5,
                # markeredgecolor=color,
                # markerfacecolor=color,
                label=label_with_count
            )
            edge_legend_handles.append(arrow_line)

        all_legend_handles = legend_handles + edge_legend_handles
        if all_legend_handles:
            ncol = math.ceil(len(all_legend_handles) / 2)
            plt.legend(handles=all_legend_handles,
                       loc='lower center',
                       bbox_to_anchor=(0.5, 0.94),
                       ncol=ncol,
                       fancybox=True,
                       shadow=True,
                       fontsize=8.5,
                       columnspacing=1.0,
                       handletextpad=0.2,
                       labelspacing=0.6
                       )

        elif color_by == 'compliance_score' and nodes_plot:
            cbar = plt.colorbar(nodes_plot, ax=plt.gca(), orientation='vertical', pad=0.02)
            cbar.set_label('Compliance Score')

        plt.axis('off')
        plt.tight_layout(rect=[0, 0, 1, 0.99]) # Adjust rect to make space at the top for title and legend

        # Save as PDF with layout name appended
        filename = f"network_{G.number_of_nodes()}_{link_type}_{color_by}_{layout_name}.pdf"
        plt.savefig(filename, format='pdf')
        plt.close()
        print(f"Saved {filename}")


def draw_static_network(network_data, link_type='references', color_by='group'):
    G = nx.DiGraph()

    # Add nodes with attributes
    for node in network_data['nodes']:
        G.add_node(
            node['id'],
            group=node.get('group', '(not specified)') or '(not specified)',
            compliance_score=node.get('compliance_score', 0)
        )

    # Add edges for the selected link type
    for link in network_data['links'].get(link_type, []):
        G.add_edge(link['source'], link['target'])

    # Use Graphviz layout for better spacing
    pos = nx.spring_layout(G, k=0.3, iterations=100, scale=2.5, seed=42)

    group_attr = nx.get_node_attributes(G, 'group')
    group_counts = Counter(group_attr.values())

    # Sort groups by count in descending order for legend
    sorted_groups = sorted(group_counts.items(), key=lambda item: item[1], reverse=True)
    sorted_group_names = [group for group, count in sorted_groups]

    node_colors = []
    cmap = None
    vmin = None
    vmax = None
    handles = []

    if color_by == 'group':
        # Get default colors from matplotlib's property cycle
        default_colors = plt.rcParams['axes.prop_cycle'].by_key()['color']

        # Create a mapping from group name to an index for coloring
        group_to_index_map = {group: i for i, group in enumerate(sorted_group_names)}

        # Assign an integer value to each node based on its group's index
        node_color_indices = [group_to_index_map[group_attr[node]] for node in G.nodes()]

        # Create a ListedColormap from the default colors
        if len(sorted_group_names) > len(default_colors):
            extended_colors = [default_colors[i % len(default_colors)] for i in range(len(sorted_group_names))]
            cmap = ListedColormap(extended_colors)
        else:
            cmap = ListedColormap(default_colors[:len(sorted_group_names)])

        node_colors = node_color_indices
        vmin = 0
        vmax = len(sorted_group_names) - 1

        # Prepare handles for the legend, ensuring they are in sorted_group_names order
        for i, group in enumerate(sorted_group_names):
            count = group_counts[group] # Get the count for the current group
            label_with_count = f"{group} $(n={count})$" # Format the label with count
            color_for_legend = cmap(i / (len(sorted_group_names) - 1) if len(sorted_group_names) > 1 else 0.5)
            handles.append(
                plt.Line2D([], [], marker='o', color='w', label=label_with_count, # Use the new label
                           markerfacecolor=color_for_legend, markersize=10)
            )

    elif color_by == 'compliance_score':
        compliance_scores = nx.get_node_attributes(G, 'compliance_score')
        node_colors = [compliance_scores[node] for node in G.nodes()]
        cmap = cm.viridis
        vmin = min(node_colors) if node_colors else 0
        vmax = max(node_colors) if node_colors else 1
    else:
        node_colors = ['grey'] * len(G.nodes())

    # Draw figure
    plt.figure(figsize=(10, 10))
    nodes = nx.draw_networkx_nodes(
        G, pos, node_size=300, node_color=node_colors, cmap=cmap, alpha=0.85, vmin=vmin, vmax=vmax,
        edgecolors='black', linewidths=1.5
    )
    nx.draw_networkx_edges(
        G, pos, alpha=0.4, arrows=True, arrowstyle='-|>', min_source_margin=10, min_target_margin=10
    )
    nx.draw_networkx_labels(
        G, pos, font_size=8, font_color="black", font_weight='bold'
    )

    # Optional legend for groups or colorbar for compliance_score
    if color_by == 'group' and handles:
        plt.legend(handles=handles, loc='lower left', title="BIP Layer")
    elif color_by == 'compliance_score' and nodes:
        cbar = plt.colorbar(nodes, ax=plt.gca(), orientation='vertical', pad=0.02)
        cbar.set_label('Compliance Score')

    plt.title(f"BIP Network - Link Type: {link_type} | Colored by: {color_by}")
    plt.axis('off')

    plt.tight_layout()

    # Save as PDF
    filename = f"network_{link_type}_{color_by}.pdf"
    plt.savefig(filename, format='pdf')
    plt.close()

# Load the pickle file
with open('./../network_data.pkl', 'rb') as f:
    data = pickle.load(f)

bips_known_explicit = []

my_bips_of_interest = [
    9, 20, 21, 32, 37, 60, 74, 84, 118, 141, 142, 151, 173, 174, 324,
    342, 350, 352, 370, 372, 374, 375,
]

my_bips_to_exclude = [
    13, 16, 30, 34, 38, 39, 47, 50, 65, 66, 68, 70, 78, 80, 81,  132, 144, 150, 151, 324, 353, 85, 91, 72, 347, 113,
    152, 300 , 330 , 124, 109, 8, 371, 75, 152, 380, 90, 339, 49, 86, 45, 48, 46, 329, 390, 157, 60, 117, 116, 136,
    119, 31, 37, 74, 112,141,143,145,147,43,44,87, 158,114,320,351,121,149,115,111,120,127,175,388,325
]


edge_type_styles = {
    'references': {
        'color': 'black', 'style': 'solid', 'alpha': 0.6,
        'label': 'regex reference'
    },
    'requires': {
        'color': 'red', 'style': 'solid', 'alpha': 0.0,
        'label': 'requires'
    },
    'replaces': {
        'color': 'blue', 'style': 'solid', 'alpha': 0.0,
        'label': 'replaces'
    },
    'superseded_by': {
        'color': 'green', 'style': 'solid', 'alpha': 0.0,
        'label': 'superseded'
    }
}

# Generate the plots
draw_static_network_with_layouts(data,
                                 link_type=['references', 'requires', 'replaces', 'superseded_by'],
                                 color_by='group',
                                 bips_to_show=my_bips_of_interest,
                                 bips_to_exclude=my_bips_to_exclude,
                                 full_title='Selected BIPs with Implicit Interdependencies found through regex search',
                                 edge_type_styles=edge_type_styles)

edge_type_styles = {
    'references': {'color': 'black', 'style': 'solid', 'alpha': 0.0, 'label': 'regex reference'},  # invisible
    'requires': {'color': 'red', 'style': 'solid', 'alpha': 1.0},
    'replaces': {'color': 'blue', 'style': 'solid', 'alpha': 1.0},
    'superseded_by': {'color': 'green', 'style': 'solid', 'alpha': 1.0, 'label': 'superseded'},
}

draw_static_network_with_layouts(data,
                                 link_type=['requires', 'replaces', 'superseded_by','references'],
                                 color_by='group',
                                 bips_to_show=my_bips_of_interest,
                                 bips_to_exclude=my_bips_to_exclude,
                                 full_title='Selected BIPs with Explicit Interdependencies according to Preamble',
                                 edge_type_styles=edge_type_styles)



draw_static_network_with_layouts(data,
                                 link_type=['references'],
                                 color_by='group',
                                 bips_to_show=None,
                                 bips_to_exclude=None,
                                 full_title='Selected BIPs with Implicit Interdependencies found through regex search',
                                 edge_type_styles=None)


draw_static_network_with_layouts(data,
                                 link_type=[ 'references', 'requires', 'replaces', 'superseded_by'],
                                 color_by='group',
                                 bips_to_show=None,
                                 bips_to_exclude=None,
                                 full_title='Selected BIPs with Explicit Interdependencies according to Preamble',
                                 edge_type_styles=None)