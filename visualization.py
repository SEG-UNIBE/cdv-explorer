import os
import json
import plotly.graph_objects as go
import networkx as nx

# Function to load all JSON files from a directory
def load_bip_data_from_folder(folder_path):
    bip_data = {}
    for file in os.listdir(folder_path):
        if file.endswith(".json"):
            file_path = os.path.join(folder_path, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    preamble = data.get("raw", {}).get("preamble", {})
                    bip_id = preamble.get("bip", "Unknown")
                    bip_data[bip_id] = preamble
                    # Add contributors if metadata exists
                    metadata = data.get("metadata", {})
                    bip_data[bip_id]["contributors"] = metadata.get("contributors", 0)
            except KeyError as e:
                print(f"KeyError: {e} in file: {file_path}")
                continue
            except json.JSONDecodeError as e:
                print(f"JSONDecodeError: {e} in file: {file_path}")
                continue
    return bip_data

# Load BIP data from the specified folder
folder_path = "bips_json"
bip_data = load_bip_data_from_folder(folder_path)

# Build the graph with error checking
G = nx.DiGraph()

for bip_id, preamble in bip_data.items():
    try:
        G.add_node(
            bip_id,
            title=preamble.get("title", "N/A"),
            status=preamble.get("status", "N/A"),
            layer=preamble.get("layer", "N/A"),
            contributors=preamble.get("contributors", 0)
        )
        # Add edges with error checking
        if preamble.get("requires"):
            for required in preamble["requires"].split(","):
                required = required.strip()
                if required:
                    G.add_edge(required, bip_id, relation="requires")
        if preamble.get("replaces"):
            for replaced in preamble["replaces"].split(","):
                replaced = replaced.strip()
                if replaced:
                    G.add_edge(replaced, bip_id, relation="replaces")
        if preamble.get("superseded_by"):
            for superseded in preamble["superseded_by"].split(","):
                superseded = superseded.strip()
                if superseded:
                    G.add_edge(bip_id, superseded, relation="superseded_by")
    except KeyError as e:
        print(f"KeyError: {e} for BIP {bip_id}")
    except Exception as e:
        print(f"Unexpected error for BIP {bip_id}: {e}")

# Extract positions for the new graph
pos = nx.spring_layout(G, seed=42)

# Create Plotly traces for edges
edge_x = []
edge_y = []
for edge in G.edges(data=True):
    x0, y0 = pos[edge[0]]
    x1, y1 = pos[edge[1]]
    edge_x.extend([x0, x1, None])
    edge_y.extend([y0, y1, None])

edge_trace = go.Scatter(
    x=edge_x,
    y=edge_y,
    line=dict(width=1, color="#888"),
    hoverinfo="none",
    mode="lines"
)

# Create Plotly traces for nodes
node_x = []
node_y = []
node_text = []
node_color = []
node_size = []
for node in G.nodes(data=True):
    x, y = pos[node[0]]
    node_x.append(x)
    node_y.append(y)
    node_info = (
        f"BIP {node[0]}<br>Title: {node[1].get('title', 'N/A')}<br>Status: {node[1].get('status', 'N/A')}<br>"
        f"Layer: {node[1].get('layer', 'N/A')}<br>Contributors: {node[1].get('contributors', 0)}"
    )
    node_text.append(node_info)
    status = node[1].get("status", "Unknown")  # Standardwert für fehlende Status
    if status == "Final":
        node_color.append("green")
    elif status == "Withdrawn":
        node_color.append("red")
    elif status == "Replaced":
        node_color.append("blue")
    elif status == "Deferred":
        node_color.append("purple")
    else:
        node_color.append("yellow")
    node_size.append(10 + 5 * node[1].get('contributors', 0))  # Größe basierend auf Mitwirkenden


node_trace = go.Scatter(
    x=node_x,
    y=node_y,
    mode="markers",
    hoverinfo="text",
    marker=dict(
        color=node_color,
        size=node_size,
        line_width=2
    ),
    text=node_text
)

# Create the final figure
fig = go.Figure(data=[edge_trace, node_trace],
                layout=go.Layout(
                    title="BIP Relationships with Contribution Scaling",
                    titlefont_size=16,
                    showlegend=False,
                    hovermode="closest",
                    margin=dict(b=0, l=0, r=0, t=40),
                    xaxis=dict(showgrid=False, zeroline=False),
                    yaxis=dict(showgrid=False, zeroline=False)
                ))

# Save the updated figure as an HTML file
output_folder = "bips_visualization"
output_path = os.path.join(output_folder, "bip_relationships_contribution_scaled.html")

# Check if the folder exists, and create it if it doesn't
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

fig.write_html(output_path)
print(f"Visualization saved to {output_path}")
