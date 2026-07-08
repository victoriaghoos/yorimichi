"""
Composition root: the only place in the codebase that knows which concrete
Infrastructure implementations back which Domain ports. Wires everything
together for both the CLI demo and the FastAPI server.
"""

import matplotlib.pyplot as plt

from yorimichi.application.plan_route_use_case import PlanScenicRouteUseCase
from yorimichi.infrastructure.osmnx_graph_repository import OSMnxGraphRepository
from yorimichi.infrastructure.osmnx_scenic_data_provider import OSMnxScenicDataProvider
from yorimichi.infrastructure.visualization import print_route_comparison, plot_route_comparison
from yorimichi.infrastructure import fastapi_app

PLACE = "Higashiyama Ward, Kyoto, Japan"

TEST_PAIRS = [
    ("Kiyomizu-dera to Yasaka Shrine", (34.9949, 135.7850), (35.0038, 135.7788)),
    ("Kiyomizu-dera to Kodai-ji", (34.9949, 135.7850), (35.0028, 135.7795)),
    ("Yasaka Shrine to Chion-in", (35.0038, 135.7788), (35.0053, 135.7830)),
    ("Kiyomizu-dera to Nanzen-ji", (34.9949, 135.7850), (35.0114, 135.7935)),
]


def build_use_case() -> tuple[PlanScenicRouteUseCase, OSMnxGraphRepository]:
    graph_repo = OSMnxGraphRepository()
    scenic_provider = OSMnxScenicDataProvider()
    use_case = PlanScenicRouteUseCase(graph_repo, scenic_provider)
    return use_case, graph_repo


api_use_case, _ = build_use_case()
fastapi_app.configure(api_use_case)
app = fastapi_app.app


def run_cli_demo():
    use_case, graph_repo = build_use_case()

    print(f"Fetching graph for: {PLACE}")
    graph = graph_repo.get_graph(PLACE)
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
    run_cli_demo()