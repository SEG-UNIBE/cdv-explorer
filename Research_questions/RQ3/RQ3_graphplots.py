import pickle
import networkx as nx
import matplotlib.pyplot as plt
from collections import Counter
import matplotlib.cm as cm
import numpy as np
from matplotlib.colors import ListedColormap # Import ListedColormap

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
    pos = nx.spring_layout(G, k=0.1, iterations=100, scale=2.5, seed=42)

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
            label_with_count = f"{group} [n={count}]" # Format the label with count
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
    plt.figure(figsize=(12, 8))
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

# Generate the plots
draw_static_network(data, link_type='references', color_by='group')
draw_static_network(data, link_type='requires', color_by='group')
draw_static_network(data, link_type='dependencies', color_by='group')