import math
import pickle
import networkx as nx
import matplotlib.pyplot as plt
from collections import Counter
import matplotlib.cm as cm
import numpy as np
from matplotlib.colors import ListedColormap # Import ListedColormap


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

def draw_static_network_with_layouts(network_data, link_type='references', color_by='group'):
    """
    Draws static network plots using various layout algorithms.

    Args:
        network_data (dict): Dictionary containing 'nodes' and 'links' data.
        link_type (str): The type of links to visualize (e.g., 'references').
        color_by (str): Attribute to color nodes by ('group' or 'compliance_score').
    """
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

    # Prepare coloring information (done once outside the loop for efficiency)
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
            label_with_count = f"{group} [n={count}]"
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
        {'name': 'spring_default', 'algo': 'spring', 'params': {'k': 0.5, 'iterations': 100, 'seed': 42}},
        {'name': 'spring_spread', 'algo': 'spring', 'params': {'k': 0.9, 'iterations': 100, 'seed': 42}},
        {'name': 'kamada_kawai', 'algo': 'kamada_kawai', 'params': {}},
        {'name': 'spectral', 'algo': 'spectral', 'params': {}},
        {'name': 'circular', 'algo': 'circular', 'params': {}},
        {'name': 'shell', 'algo': 'shell', 'params': {}},
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
            elif config['algo'] == 'spectral':
                pos = nx.spectral_layout(G, **config['params'])
            elif config['algo'] == 'circular':
                pos = nx.circular_layout(G, **config['params'])
            elif config['algo'] == 'shell':
                pos = nx.shell_layout(G, **config['params'])
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
        plt.figure(figsize=(12, 8))
        nodes_plot = nx.draw_networkx_nodes(
            G, pos, node_size=300, node_color=node_colors_data, cmap=cmap_for_plot, alpha=0.85,
            vmin=vmin_for_plot, vmax=vmax_for_plot, edgecolors='black', linewidths=1.5
        )
        nx.draw_networkx_edges(
            G, pos, alpha=0.4, arrows=True, arrowstyle='-|>', min_source_margin=10, min_target_margin=10
        )
        nx.draw_networkx_labels(
            G, pos, font_size=8, font_color="black", font_weight='bold'
        )

        # Determine the dynamic part of the title based on link_type
        if link_type == 'requires':
            dependency_description = "explicit dependencies declared in preamble"
        elif link_type == 'references':
            dependency_description = "implicit dependencies found using regex in entire document"
        elif link_type == 'dependencies': # Assuming 'dependey' is a typo and should be 'dependency' or similar
            dependency_description = "implicit dependencies extracted using LLM in entire document"
        else:
            dependency_description = f"dependencies of type '{link_type}'" # Fallback for unknown types

        # Construct the full title
        full_title = f"BIP Catalog with {dependency_description}"
        # Set the main plot title
        plt.title(full_title,
                  pad=50,
                  y=1.02
                  ) # Increased 'y' to position it higher, giving more room for legend below it


        # Optional legend for groups or colorbar for compliance_score
        if color_by == 'group' and legend_handles:
            # Calculate ncol to roughly create two rows
            num_legend_items = len(legend_handles)
            legend_ncol = math.ceil(num_legend_items / 2) # Half the items per row, rounded up

            # Place the legend horizontally, below the title
            plt.legend(handles=legend_handles,
                       loc='lower center',
                       bbox_to_anchor=(0.5, 1.00), # Still good for placing just above plot
                       ncol=legend_ncol,         # Set to create two rows
                       title="BIP Layer",
                       fancybox=True,
                       shadow=True,
                       columnspacing=1.0,
                       handletextpad=0.5,
                       labelspacing=0.2
                       )
        elif color_by == 'compliance_score' and nodes_plot:
            cbar = plt.colorbar(nodes_plot, ax=plt.gca(), orientation='vertical', pad=0.02)
            cbar.set_label('Compliance Score')

        plt.axis('off')
        plt.tight_layout(rect=[0, 0, 1, 0.95]) # Adjust rect to make space at the top for title and legend

        # Save as PDF with layout name appended
        filename = f"network_{link_type}_{color_by}_{layout_name}.pdf"
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
draw_static_network_with_layouts(data, link_type='references', color_by='group')
draw_static_network_with_layouts(data, link_type='requires', color_by='group')
draw_static_network_with_layouts(data, link_type='dependencies', color_by='group')