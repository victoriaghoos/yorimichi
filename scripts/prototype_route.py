import osmnx as ox
import matplotlib.pyplot as plt

from yorimichi.application.plan_route_use_case import PlanScenicRouteUseCase
from yorimichi.infrastructure.osmnx_graph_repository import OSMnxGraphRepository
from yorimichi.infrastructure.osmnx_scenic_data_provider import OSMnxScenicDataProvider

PLACE = "Higashiyama Ward, Kyoto, Japan"

TEST_PAIRS = [
    ("Kiyomizu-dera to Yasaka Shrine", (34.9949, 135.7850), (35.0038, 135.7788)),
    ("Kiyomizu-dera to Kodai-ji", (34.9949, 135.7850), (35.0028, 135.7795)),
    ("Yasaka Shrine to Chion-in", (35.0038, 135.7788), (35.0053, 135.7830)),
    ("Kiyomizu-dera to Nanzen-ji", (34.9949, 135.7850), (35.0114, 135.7935)),
]


def print_route_comparison(label, result):
    diff = result.scenic_route.length - result.baseline_route.length
    print(
        f"{label}: baseline={result.baseline_route.length:.1f}m, "
        f"scenic={result.scenic_route.length:.1f}m, diff={diff:+.1f}m"
    )


def plot_route_comparison(graph, result, label):
    """
    Plot baseline vs scenic route for a single pair, zoomed to the relevant area
    with a legend, so the divergence is clearly visible without extra context.
    """
    baseline_ids = [int(n) for n in result.baseline_route.node_ids]
    scenic_ids = [int(n) for n in result.scenic_route.node_ids]

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


def main():
    graph_repo = OSMnxGraphRepository()
    scenic_provider = OSMnxScenicDataProvider()
    use_case = PlanScenicRouteUseCase(graph_repo, scenic_provider)

    print(f"Fetching graph for: {PLACE}")
    graph = graph_repo.get_graph(PLACE)  # fetched once here, purely for visualization later
    print(f"Nodes: {len(graph.nodes)}, Edges: {len(graph.edges)}")

    print("\nComparing baseline vs scenic routes across multiple point pairs:")
    results = {}
    for label, orig_point, dest_point in TEST_PAIRS:
        result = use_case.execute(PLACE, orig_point, dest_point)
        print_route_comparison(label, result)
        results[label] = result

    for label, result in results.items():
        plot_route_comparison(graph, result, label)

    plt.show()


if __name__ == "__main__":
    main()