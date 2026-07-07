"""
Application layer: orchestrates scenic route planning. No networkx, no infrastructure imports, no raw graph objects returned: this is the "Load, Do, Return" orchestration boundary.
"""

from dataclasses import dataclass

from yorimichi.domain.entities import Route
from yorimichi.domain.repositories import IGraphRepository, IScenicDataProvider


@dataclass(frozen=True)
class PlanRouteResult:
    baseline_route: Route
    scenic_route: Route


class PlanScenicRouteUseCase:
    def __init__(self, graph_repo: IGraphRepository, scenic_provider: IScenicDataProvider):
        self._graph_repo = graph_repo
        self._scenic_provider = scenic_provider

    def execute(self, place: str, orig_point: tuple[float, float], dest_point: tuple[float, float]) -> PlanRouteResult:
        graph = self._graph_repo.get_graph(place)
        self._scenic_provider.load(place)

        orig_node = self._graph_repo.nearest_node(graph, orig_point[0], orig_point[1])
        dest_node = self._graph_repo.nearest_node(graph, dest_point[0], dest_point[1])

        baseline_route = self._graph_repo.find_shortest_route(graph, orig_node, dest_node)
        scenic_route = self._graph_repo.find_scenic_route(graph, orig_node, dest_node, self._scenic_provider)

        return PlanRouteResult(baseline_route=baseline_route, scenic_route=scenic_route)