import networkx as nx
import pytest

from yorimichi.application.plan_route_use_case import PlanRouteResult, PlanScenicRouteUseCase
from yorimichi.domain.entities import Node, Route
from yorimichi.domain.exceptions import CoordinatesOutOfRangeException
from yorimichi.infrastructure.osmnx_graph_repository import OSMnxGraphRepository


class FakeGraphRepository:
    """
    Fake IGraphRepository: delegates routing logic to a real OSMnxGraphRepository
    instance internally (acting on a small hand-built graph), so the fake stays
    thin while still exercising real find_shortest_route/find_scenic_route logic.
    """
    def __init__(self, graph):
        self._graph = graph
        self._real_repo = OSMnxGraphRepository()

    def get_graph(self, orig_point, dest_point):
        return self._graph

    def nearest_node(self, graph, lat, lon):
        best_id, best_dist = None, float("inf")
        for node_id, data in graph.nodes(data=True):
            dist = (data["y"] - lat) ** 2 + (data["x"] - lon) ** 2
            if dist < best_dist:
                best_id, best_dist = node_id, dist
        data = graph.nodes[best_id]
        return Node(id=str(best_id), lat=data["y"], lon=data["x"])

    def find_shortest_route(self, graph, orig, dest):
        return self._real_repo.find_shortest_route(graph, orig, dest)

    def find_scenic_route(self, graph, orig, dest, scenic_index):
        return self._real_repo.find_scenic_route(graph, orig, dest, scenic_index)


class FakeScenicIndex:
    def __init__(self, fixed_penalty):
        self.fixed_penalty = fixed_penalty

    def get_scenic_penalty(self, lat, lon):
        return self.fixed_penalty


class FakeScenicDataProvider:
    """Fake IScenicDataProvider returning an immutable scenic index object."""
    def __init__(self, fixed_penalty=1.0):
        self.fixed_penalty = fixed_penalty
        self.loaded_orig_point = None
        self.loaded_dest_point = None
        self.loaded_category_boosts = None

    def load(self, orig_point, dest_point, category_boosts=None):
        self.loaded_orig_point = orig_point
        self.loaded_dest_point = dest_point
        self.loaded_category_boosts = category_boosts
        return FakeScenicIndex(self.fixed_penalty)


@pytest.fixture
def simple_graph():
    G = nx.MultiDiGraph(crs="EPSG:4326")
    G.add_node(1, y=35.000, x=135.000)
    G.add_node(2, y=35.001, x=135.000)
    G.add_node(3, y=35.000, x=135.001)
    G.add_node(4, y=35.001, x=135.001)

    edges = [(1, 2), (2, 4), (1, 3), (3, 4)]
    for u, v in edges:
        G.add_edge(u, v, length=100)
        G.add_edge(v, u, length=100)
    return G


def test_execute_returns_plan_route_result(simple_graph):
    """Confirms execute() returns a proper PlanRouteResult with Route entities, not raw dicts/graphs."""
    graph_repo = FakeGraphRepository(simple_graph)
    scenic_provider = FakeScenicDataProvider(fixed_penalty=1.0)
    use_case = PlanScenicRouteUseCase(graph_repo, scenic_provider)

    result = use_case.execute((35.000, 135.000), (35.001, 135.001))

    assert isinstance(result, PlanRouteResult)
    assert isinstance(result.baseline_route, Route)
    assert isinstance(result.scenic_route, Route)
    assert result.baseline_route.node_ids[0] == "1"
    assert result.baseline_route.node_ids[-1] == "4"
    assert result.scenic_route.node_ids[0] == "1"
    assert result.scenic_route.node_ids[-1] == "4"
    assert len(result.baseline_coordinates) == len(result.baseline_route.node_ids)
    assert len(result.scenic_coordinates) == len(result.scenic_route.node_ids)


def test_execute_loads_scenic_data_for_the_given_corridor(simple_graph):
    """Confirms the use case calls scenic_provider.load() with route coordinates."""
    graph_repo = FakeGraphRepository(simple_graph)
    scenic_provider = FakeScenicDataProvider()
    use_case = PlanScenicRouteUseCase(graph_repo, scenic_provider)

    orig = (35.000, 135.000)
    dest = (35.001, 135.001)
    use_case.execute(orig, dest)

    assert scenic_provider.loaded_orig_point == orig
    assert scenic_provider.loaded_dest_point == dest


def test_execute_passes_category_boosts_to_scenic_provider(simple_graph):
    graph_repo = FakeGraphRepository(simple_graph)
    scenic_provider = FakeScenicDataProvider()
    use_case = PlanScenicRouteUseCase(graph_repo, scenic_provider)

    boosts = {"nature": 1.5, "shrines_temples": 0.7}
    use_case.execute((35.000, 135.000), (35.001, 135.001), boosts)

    assert scenic_provider.loaded_category_boosts == boosts


def test_execute_never_exposes_raw_graph():
    """
    Confirms PlanRouteResult has no 'graph' attribute: the use case must not
    leak the raw networkx object out to callers (UI, API, etc.).
    """
    assert not hasattr(PlanRouteResult, "graph")
    fields = PlanRouteResult.__dataclass_fields__
    assert "graph" not in fields
    assert set(fields.keys()) == {
        "baseline_route",
        "scenic_route",
        "baseline_coordinates",
        "scenic_coordinates",
    }


def test_execute_raises_when_origin_coordinates_are_far_from_graph(simple_graph):
    """
    Confirms the use case rejects coordinates unreasonably far from the graph,
    rather than silently returning a meaningless "nearest node" route (the
    real-world bug found via the (0, 0) coordinates test in the API).
    """
    graph_repo = FakeGraphRepository(simple_graph)
    scenic_provider = FakeScenicDataProvider(fixed_penalty=1.0)
    use_case = PlanScenicRouteUseCase(graph_repo, scenic_provider)

    with pytest.raises(CoordinatesOutOfRangeException):
        use_case.execute((0.0, 0.0), (35.001, 135.001))


def test_execute_raises_when_destination_coordinates_are_far_from_graph(simple_graph):
    """Same check, but for the destination coordinate instead of the origin."""
    graph_repo = FakeGraphRepository(simple_graph)
    scenic_provider = FakeScenicDataProvider(fixed_penalty=1.0)
    use_case = PlanScenicRouteUseCase(graph_repo, scenic_provider)

    with pytest.raises(CoordinatesOutOfRangeException):
        use_case.execute((35.000, 135.000), (0.0, 0.0))