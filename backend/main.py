"""
Composition root
"""

import os

from dotenv import load_dotenv
import matplotlib.pyplot as plt

from yorimichi.application.plan_route_use_case import PlanScenicRouteUseCase
from yorimichi.domain.repositories import IGraphRepository
from yorimichi.infrastructure.osmnx_graph_repository import OSMnxGraphRepository
from yorimichi.infrastructure.postgis_graph_repository import PostGISGraphRepository
from yorimichi.infrastructure.osmnx_scenic_data_provider import OSMnxScenicDataProvider
from yorimichi.infrastructure.visualization import print_route_comparison, plot_route_comparison
from yorimichi.infrastructure import fastapi_app

load_dotenv()

PLACE = "Higashiyama Ward, Kyoto, Japan"

TEST_PAIRS = [
    ("Kiyomizu-dera to Yasaka Shrine", (34.9949, 135.7850), (35.0038, 135.7788)),
    ("Kiyomizu-dera to Kodai-ji", (34.9949, 135.7850), (35.0028, 135.7795)),
    ("Yasaka Shrine to Chion-in", (35.0038, 135.7788), (35.0053, 135.7830)),
    ("Kiyomizu-dera to Nanzen-ji", (34.9949, 135.7850), (35.0114, 135.7935)),
]


def build_graph_repo() -> IGraphRepository:
    backend = os.environ.get("YORIMICHI_GRAPH_BACKEND", "osmnx").lower()

    if backend == "postgis":
        database_url = os.environ.get("POSTGIS_DATABASE_URL")
        if not database_url:
            raise RuntimeError(
                "YORIMICHI_GRAPH_BACKEND=postgis but POSTGIS_DATABASE_URL is not set. "
                "Set it in your .env file or environment."
            )
        print("Using PostGISGraphRepository backend.")
        return PostGISGraphRepository(database_url)

    print("Using OSMnxGraphRepository backend.")
    return OSMnxGraphRepository()


def build_use_case() -> tuple[PlanScenicRouteUseCase, IGraphRepository]:
    graph_repo = build_graph_repo()
    scenic_provider = OSMnxScenicDataProvider()
    use_case = PlanScenicRouteUseCase(graph_repo, scenic_provider)
    return use_case, graph_repo

_use_case, _graph_repo = build_use_case()

fastapi_app.configure(_use_case)
app = fastapi_app.app


def run_cli_demo():
    print("\nComparing baseline vs scenic routes across multiple point pairs:")
    results = {}
    graphs_by_label = {}
    for label, orig_point, dest_point in TEST_PAIRS:
        graph = _graph_repo.get_graph(PLACE, orig_point=orig_point, dest_point=dest_point)
        print(f"{label}: subgraph nodes={len(graph.nodes)}, edges={len(graph.edges)}")
        result = _use_case.execute(PLACE, orig_point, dest_point)
        print_route_comparison(label, result)
        results[label] = result
        graphs_by_label[label] = graph

    for label, result in results.items():
        graph = graphs_by_label[label]
        plot_route_comparison(graph, result, label)

    plt.show()


if __name__ == "__main__":
    run_cli_demo()