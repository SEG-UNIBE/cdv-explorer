import os
import json
import networkx as nx
import plotly.graph_objects as go
from wordcloud import WordCloud
import dash
from dash import dcc, html, Input, Output
import matplotlib.pyplot as plt
import io
import base64


# Funktion zum Laden der BIP-Daten
from collections import Counter

def load_bip_data(folder_path):
    bip_data = {}
    unique_statuses = set()
    aggregated_word_counter = Counter()  # To store combined word counts

    for file in os.listdir(folder_path):
        if file.endswith(".json"):
            file_path = os.path.join(folder_path, file)
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                raw = data.get("raw", {}).get("preamble", {})
                metadata = data.get("metadata", {})
                insights = data.get("insights", {})

                # Extract BIP data
                status = raw.get("status", "Unknown")
                contributors = metadata.get("contributors", 0)

                bip_id = raw.get("bip", "Unknown")
                bip_data[bip_id] = {
                    "title": raw.get("title", "N/A"),
                    "status": status,
                    "contributors": contributors,
                    "requires": raw.get("requires", ""),
                    "replaces": raw.get("replaces", ""),
                    "superseded_by": raw.get("superseded_by", ""),
                }

                # Update statuses
                unique_statuses.add(status)

                # Aggregate word counts
                word_list = insights.get("word_list", {})
                aggregated_word_counter.update(word_list)

    return bip_data, sorted(unique_statuses), dict(aggregated_word_counter)





# Funktion zum Erstellen eines interaktiven Graphen
def create_graph(bip_data, selected_status, size_scale):
    G = nx.DiGraph()

    # Alle BIPs in den Graphen laden
    for bip_id, preamble in bip_data.items():
        G.add_node(
            bip_id,
            title=preamble.get("title", "N/A"),
            status=preamble.get("status", "Unknown"),
            contributors=preamble.get("contributors", 0),
        )
        if preamble.get("requires"):
            for required in preamble["requires"].split(","):
                required = required.strip()
                # Normalize the required field by removing "BIP-" prefix if it exists
                if required.lower().startswith("bip-"):
                    required = required[4:]  # Remove the first 4 characters ("BIP-")
                if required:
                    G.add_edge(required, bip_id, relation="requires")

        if preamble.get("replaces"):
            for replaced in preamble["replaces"].split(","):
                replaced = replaced.strip()
                # Normalize the required field by removing "BIP-" prefix if it exists
                if replaced.lower().startswith("bip-"):
                    replaced = replaced[4:]  # Remove the first 4 characters ("BIP-")
                if replaced:
                    G.add_edge(replaced, bip_id, relation="replaces")
        if preamble.get("superseded_by"):
            for superseded in preamble["superseded_by"].split(","):
                superseded = superseded.strip()
                # Normalize the required field by removing "BIP-" prefix if it exists
                if superseded.lower().startswith("bip-"):
                    superseded = superseded[4:]  # Remove the first 4 characters ("BIP-")
                if superseded:
                    G.add_edge(bip_id, superseded, relation="superseded_by")

    # Filterknoten
    visible_nodes = {n for n, d in G.nodes(data=True) if selected_status == "All" or d.get("status", "Unknown") == selected_status}
    visible_edges = [(u, v, G[u][v]) for u, v in G.edges if u in visible_nodes or v in visible_nodes]

    # Positionen der Knoten bestimmen
    pos = nx.spring_layout(G, seed=42)

    # Kanten zeichnen (mit Pfeilen)
    edge_traces = []
    annotations = []  # Pfeilspitzen
    for u, v, data in visible_edges:
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        relation = data.get("relation", "unknown")

        if relation == "replaces":
            line_style = "dot"
            line_color = "blue"
            # Pfeil hinzufügen
            annotations.append(dict(
                ax=x0, ay=y0, x=x1, y=y1,
                xref='x', yref='y', axref='x', ayref='y',
                showarrow=True, arrowhead=3, arrowsize=2, arrowwidth=1, arrowcolor="blue"
            ))
        elif relation == "requires":
            line_style = "solid"
            line_color = "black"
        else:
            line_style = "solid"
            line_color = "gray"

        edge_traces.append(go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            line=dict(width=2, dash=line_style, color=line_color),
            mode="lines",
            hoverinfo="none"
        ))

    # Knoten zeichnen
    node_x = []
    node_y = []
    node_text = []
    node_color = []
    node_size = []

    # Statusfarben festlegen
    status_colors = {
        "Final": "green",
        "Withdrawn": "red",
        "Replaced": "blue",
        "Deferred": "purple",
        "Rejected": "orange",
        "Draft": "pink",
        "Proposed": "cyan",
        "Unknown": "yellow"
    }

    for node, data in G.nodes(data=True):
        x, y = pos[node]
        if node in visible_nodes:  # Nur sichtbare Knoten
            node_x.append(x)
            node_y.append(y)
            node_info = (
                f"BIP {node}<br>Title: {data.get('title', 'N/A')}<br>Status: {data.get('status', 'Unknown')}<br>"
                f"Contributors: {data.get('contributors', 0)}"
            )
            node_text.append(node_info)
            status = data.get("status", "Unknown")
            node_color.append(status_colors.get(status, "gray"))
            node_size.append(10 + size_scale * data.get("contributors", 0))

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers",
        hoverinfo="text",
        marker=dict(
            size=node_size,
            color=node_color,
            line_width=2
        ),
        text=node_text
    )

    # Dynamische Legende
    active_statuses = {d.get("status", "Unknown") for n, d in G.nodes(data=True) if n in visible_nodes}
    legend_items = []

    # Beziehungen hinzufügen (nur falls Kanten sichtbar sind)
    if any(data.get("relation") == "replaces" for u, v, data in visible_edges):
        legend_items.append(go.Scatter(
            x=[None], y=[None], mode='lines',
            line=dict(color="blue", width=2, dash="dot"), name="A replaces B"
        ))
    if any(data.get("relation") == "requires" for u, v, data in visible_edges):
        legend_items.append(go.Scatter(
            x=[None], y=[None], mode='lines',
            line=dict(color="black", width=2), name="A requires B"
        ))

    # Statusfarben hinzufügen (nur falls Knoten sichtbar sind)
    for status in active_statuses:
        legend_items.append(go.Scatter(
            x=[None], y=[None], mode='markers',
            marker=dict(size=10, color=status_colors.get(status, "gray")),
            name=status
        ))

    # Graph-Höhe vergrößern
    fig = go.Figure(data=edge_traces + [node_trace] + legend_items,
                    layout=go.Layout(
                        title="BIP Relationships",
                        showlegend=True,
                        legend=dict(x=0, y=-0.2, orientation="h"),
                        hovermode="closest",
                        margin=dict(b=0, l=0, r=0, t=40),
                        height=700,  # Höhe des Graphen erhöhen
                        xaxis=dict(showgrid=False, zeroline=False),
                        yaxis=dict(showgrid=False, zeroline=False),
                        annotations=annotations  # Pfeile
                    ))
    return fig


# Funktion zum Erstellen einer Wordcloud
def create_wordcloud(word_counter):
    # Prüfen, ob word_counter leer ist
    if not word_counter:
        print("Word counter is empty, returning placeholder image.")
        return "data:image/png;base64," + base64.b64encode(
            io.BytesIO().getvalue()
        ).decode()  # Leeres Bild zurückgeben

    # Prüfen, ob word_counter korrekt strukturiert ist
    if isinstance(word_counter, list):
        try:
            word_counter = {str(item[0]): int(item[1]) for item in word_counter if len(item) == 2}
        except Exception as e:
            print("Error processing word_counter:", e)
            word_counter = {}

    # Generiere die Wordcloud
    wordcloud = WordCloud(width=800, height=400, background_color="white").generate_from_frequencies(word_counter)
    img = io.BytesIO()
    plt.figure(figsize=(10, 5))
    plt.imshow(wordcloud, interpolation="bilinear")
    plt.axis("off")
    plt.tight_layout(pad=0)
    plt.savefig(img, format="png")
    plt.close()
    img.seek(0)
    return "data:image/png;base64," + base64.b64encode(img.getvalue()).decode()


# Lade BIP-Daten und Wortliste
folder_path = "bips_json"
bip_data, statuses, word_counter = load_bip_data(folder_path)

# Starte Dash App
app = dash.Dash(__name__)
app.layout = html.Div([
    html.H1("BIP Visualizer"),
    dcc.Graph(id="bip-graph"),
    html.Label("Filter by Status:"),
    dcc.Dropdown(
        id="status-filter",
        options=[
            {"label": "All", "value": "All"},
            {"label": "Final", "value": "Final"},
            {"label": "Withdrawn", "value": "Withdrawn"},
            {"label": "Replaced", "value": "Replaced"},
            {"label": "Deferred", "value": "Deferred"},
            {"label": "Draft", "value": "Draft"},
            {"label": "Rejected", "value": "Rejected"},
            {"label": "Active", "value": "Active"},
            {"label": "Obsolete", "value": "Obsolete"}
        ],
        value="All"
    ),
    html.Label("Node Size Scaling:"),
    dcc.Slider(
        id="node-size-scale",
        min=1,
        max=10,
        value=2,
        marks={i: f"{i}" for i in range(1, 11)}
    ),
    html.Hr(),
    html.H2("Wordcloud"),
    html.Img(id="wordcloud-image")
])


# Callbacks
@app.callback(
    Output("bip-graph", "figure"),
    [Input("status-filter", "value"),
     Input("node-size-scale", "value")]
)
def update_graph(selected_status, size_scale):
    return create_graph(bip_data, selected_status, size_scale)


@app.callback(
    Output("wordcloud-image", "src"),
    [Input("status-filter", "value")]  # Status filter input
)
def update_wordcloud(selected_status):
    # For now, Word Cloud remains static and ignores the filter.
    return create_wordcloud(word_counter)

@app.callback(
    Output("status-filter", "options"),
    Input("bip-data", "data")  # Hier setzen wir voraus, dass bip_data als State übergeben wird
)
def update_dropdown_options(bip_data):
    # Status aus den Daten extrahieren
    statuses = sorted({d["status"] for d in bip_data.values()})
    return [{"label": status, "value": status} for status in ["All"] + statuses]



# Start Server
if __name__ == "__main__":
    app.run_server(debug=True)
