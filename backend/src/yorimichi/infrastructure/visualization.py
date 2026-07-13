"""
Infrastructure adapter: rendering/output logic for route comparisons.
Depends on matplotlib/osmnx: this is where presentation-layer dependencies belong
"""

import osmnx as ox


def print_route_comparison(label, result):
    diff = result.scenic_route.length - result.baseline_route.length
    print(
        f"{label}: baseline={result.baseline_route.length:.1f}m, "
        f"scenic={result.scenic_route.length:.1f}m, diff={diff:+.1f}m"
    )


def _normalize_route_node_ids(graph, node_ids):
    """
    Normalize route node IDs against graph node key types.

    OSMnx graphs typically use int node keys, while PostGIS-backed graphs in
    this project use string keys. Route entities store node IDs as strings.
    """
    normalized = []
    for node_id in node_ids:
        if node_id in graph.nodes:
            normalized.append(node_id)
            continue

        try:
            int_id = int(node_id)
        except (ValueError, TypeError):
            normalized.append(node_id)
            continue

        normalized.append(int_id if int_id in graph.nodes else node_id)
    return normalized


def plot_route_comparison(graph, result, label):
    """
    Plot baseline vs scenic route for a single pair, zoomed to the relevant area
    with a legend, so the divergence is clearly visible without extra context.
    """
    baseline_ids = _normalize_route_node_ids(graph, result.baseline_route.node_ids)
    scenic_ids = _normalize_route_node_ids(graph, result.scenic_route.node_ids)

    fig, ax = ox.plot_graph_routes(
        graph,
        [baseline_ids, scenic_ids],
        route_colors=["red", "gold"],
        route_linewidths=3,
        node_size=0,
        show=False,
        close=False,
    )

    all_route_nodes = set(baseline_ids) | set(scenic_ids)
    lats = [graph.nodes[n]["y"] for n in all_route_nodes]
    lons = [graph.nodes[n]["x"] for n in all_route_nodes]
    margin = 0.002
    ax.set_xlim(min(lons) - margin, max(lons) + margin)
    ax.set_ylim(min(lats) - margin, max(lats) + margin)

    ax.plot([], [], color="red", linewidth=3, label="Shortest route")
    ax.plot([], [], color="gold", linewidth=3, label="Scenic route (S-A*)")
    ax.legend(loc="lower right", facecolor="black", labelcolor="white", framealpha=0.8)

    ax.set_title(label, color="white", fontsize=12)
    return fig, ax