"""
Application layer: orchestrates scenic route planning. No networkx, no
infrastructure imports, no raw graph objects returned: this is the
"Load, Do, Return" orchestration boundary.
"""

from dataclasses import dataclass

from yorimichi.domain.entities import Route
from yorimichi.domain.exceptions import CoordinatesOutOfRangeException
from yorimichi.domain.repositories import IGraphRepository, IScenicDataProvider
from yorimichi.domain.routing import haversine_distance, MAX_REASONABLE_DISTANCE_METERS


@dataclass(frozen=True)
class PlanRouteResult:
    baseline_route: Route
    scenic_route: Route
    baseline_coordinates: tuple[tuple[float, float], ...]
    scenic_coordinates: tuple[tuple[float, float], ...]


class PlanScenicRouteUseCase:
    def __init__(self, graph_repo: IGraphRepository, scenic_provider: IScenicDataProvider):
        self._graph_repo = graph_repo
        self._scenic_provider = scenic_provider

    def execute(
        self,
        place: str,
        orig_point: tuple[float, float],
        dest_point: tuple[float, float],
        categories: list[str] | None = None,
    ) -> PlanRouteResult:
        graph = self._graph_repo.get_graph(place)
        self._scenic_provider.load(place, categories)

        orig_node = self._graph_repo.nearest_node(graph, orig_point[0], orig_point[1])
        dest_node = self._graph_repo.nearest_node(graph, dest_point[0], dest_point[1])

        self._validate_within_range("Origin", orig_point, orig_node, place)
        self._validate_within_range("Destination", dest_point, dest_node, place)

        baseline_route = self._graph_repo.find_shortest_route(graph, orig_node, dest_node)
        scenic_route = self._graph_repo.find_scenic_route(graph, orig_node, dest_node, self._scenic_provider)
        baseline_coordinates = self._node_ids_to_coordinates(graph, baseline_route.node_ids)
        scenic_coordinates = self._node_ids_to_coordinates(graph, scenic_route.node_ids)

        return PlanRouteResult(
            baseline_route=baseline_route,
            scenic_route=scenic_route,
            baseline_coordinates=baseline_coordinates,
            scenic_coordinates=scenic_coordinates,
        )

    def _node_ids_to_coordinates(self, graph, node_ids: tuple[str, ...]) -> tuple[tuple[float, float], ...]:
        """
        Resolves node IDs to (lat, lon) coordinates for the given graph.

        Note: OSMnxGraphRepository stores nodes with integer IDs (networkx
        convention), while PostGISGraphRepository stores them with string
        IDs (yorimichi_nodes.id is a String column). Route.node_ids is
        always a tuple of strings (see Route entity), so this function
        normalizes by trying the string form first, then falling back to
        an int conversion for graphs built from the OSMnx backend.

        This int/string inconsistency between the two IGraphRepository
        implementations is known technical debt: ideally both backends
        would agree on a single node ID type so this fallback wouldn't be
        necessary. Left as-is for now since both backends are otherwise
        fully interchangeable and this is the only place the difference
        leaks through.
        """
        coordinates: list[tuple[float, float]] = []
        for node_id in node_ids:
            graph_node_id = node_id
            if graph_node_id not in graph.nodes:
                try:
                    graph_node_id = int(node_id)
                except (ValueError, TypeError):
                    graph_node_id = node_id
            node_data = graph.nodes[graph_node_id]
            coordinates.append((node_data["y"], node_data["x"]))
        return tuple(coordinates)

    def _validate_within_range(self, label: str, point: tuple[float, float], nearest_node, place: str):
        distance = haversine_distance(point[0], point[1], nearest_node.lat, nearest_node.lon)
        if distance > MAX_REASONABLE_DISTANCE_METERS:
            raise CoordinatesOutOfRangeException(label, point[0], point[1], distance, place)