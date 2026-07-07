import osmnx as ox
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial import cKDTree

from yorimichi.infrastructure.osmnx_routing_adapter import make_edge_weight_fn, make_heuristic_fn
from yorimichi.infrastructure.osmnx_scenic_data_provider import OSMnxScenicDataProvider
from yorimichi.infrastructure.osmnx_graph_repository import OSMnxGraphRepository

PLACE = "Higashiyama Ward, Kyoto, Japan"

TEST_PAIRS = [
    ("Kiyomizu-dera to Yasaka Shrine", (34.9949, 135.7850), (35.0038, 135.7788)),
    ("Kiyomizu-dera to Kodai-ji", (34.9949, 135.7850), (35.0028, 135.7795)),
    ("Yasaka Shrine to Chion-in", (35.0038, 135.7788), (35.0053, 135.7830)),
    ("Kiyomizu-dera to Nanzen-ji", (34.9949, 135.7850), (35.0114, 135.7935)),
]


def compute_route(graph, graph_repo, scenic_provider, orig_point, dest_point):
    """Compute both the baseline (shortest) and scenic (S-A*) routes for a coordinate pair."""
    orig_domain_node = graph_repo.nearest_node(graph, orig_point[0], orig_point[1])
    dest_domain_node = graph_repo.nearest_node(graph, dest_point[0], dest_point[1])
    orig_node = int(orig_domain_node.id)
    dest_node = int(dest_domain_node.id)

    baseline_route = nx.shortest_path(graph, orig_node, dest_node, weight="length")
    baseline_length = nx.shortest_path_length(graph, orig_node, dest_node, weight="length")

    weight_fn = make_edge_weight_fn(graph, scenic_provider)
    heuristic_fn = make_heuristic_fn(graph)
    scenic_route = nx.astar_path(graph, orig_node, dest_node, heuristic=heuristic_fn, weight=weight_fn)
    scenic_length = sum(
        graph.edges[scenic_route[i], scenic_route[i + 1], 0].get("length", 0)
        for i in range(len(scenic_route) - 1)
    )

    return {
        "baseline_route": baseline_route,
        "baseline_length": baseline_length,
        "scenic_route": scenic_route,
        "scenic_length": scenic_length,
    }


def print_route_comparison(label, result):
    diff = result["scenic_length"] - result["baseline_length"]
    print(
        f"{label}: baseline={result['baseline_length']:.1f}m, "
        f"scenic={result['scenic_length']:.1f}m, diff={diff:+.1f}m"
    )


def plot_route_comparison(graph, result, label):
    """
    Plot baseline vs scenic route for a single pair, zoomed to the relevant area
    with a legend, so the divergence is clearly visible without extra context.
    """
    fig, ax = ox.plot_graph_routes(
        graph,
        [result["baseline_route"], result["scenic_route"]],
        route_colors=["red", "gold"],
        route_linewidths=3,
        node_size=0,
        show=False,
        close=False,
    )

    all_route_nodes = set(result["baseline_route"]) | set(result["scenic_route"])
    lats = [graph.nodes[n]["y"] for n in all_route_nodes]
    lons = [graph.nodes[n]["x"] for n in all_route_nodes]
    margin = 0.002  # roughly 200m padding
    ax.set_xlim(min(lons) - margin, max(lons) + margin)
    ax.set_ylim(min(lats) - margin, max(lats) + margin)

    ax.plot([], [], color="red", linewidth=3, label="Shortest route")
    ax.plot([], [], color="gold", linewidth=3, label="Scenic route (S-A*)")
    ax.legend(loc="lower right", facecolor="black", labelcolor="white", framealpha=0.8)

    ax.set_title(label, color="white", fontsize=12)
    return fig, ax


def main():
    print(f"Fetching graph for: {PLACE}")
    graph_repo = OSMnxGraphRepository()
    graph = graph_repo.get_graph(PLACE)
    print(f"Nodes: {len(graph.nodes)}, Edges: {len(graph.edges)}")

    scenic_provider = OSMnxScenicDataProvider()
    scenic_provider.load(PLACE)

    print("\nComparing baseline vs scenic routes across multiple point pairs:")
    results = {}
    for label, orig_point, dest_point in TEST_PAIRS:
        result = compute_route(graph, graph_repo, scenic_provider, orig_point, dest_point)
        print_route_comparison(label, result)
        results[label] = result

    for label, result in results.items():
        plot_route_comparison(graph, result, label)

    plt.show()


if __name__ == "__main__":
    main()