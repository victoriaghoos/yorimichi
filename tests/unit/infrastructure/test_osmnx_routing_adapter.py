import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent / "scripts"))

import networkx as nx
import pytest

from yorimichi.infrastructure.osmnx_routing_adapter import make_edge_weight_fn, make_heuristic_fn


@pytest.fixture
def simple_graph():
    G = nx.MultiDiGraph()
    G.add_node(1, y=35.000, x=135.000)
    G.add_node(2, y=35.001, x=135.000)
    G.add_node(3, y=35.000, x=135.001)
    G.add_node(4, y=35.001, x=135.001)

    edges = [(1, 2), (2, 4), (1, 3), (3, 4)]
    for u, v in edges:
        G.add_edge(u, v, length=100)
        G.add_edge(v, u, length=100)
    return G


@pytest.fixture
def asymmetric_graph():
    G = nx.MultiDiGraph()
    G.add_node(1, y=35.000, x=135.000)
    G.add_node(2, y=35.001, x=135.000)
    G.add_node(3, y=35.000, x=135.002)
    G.add_node(4, y=35.001, x=135.002)

    short_path_edges = [(1, 2), (2, 4)]
    long_path_edges = [(1, 3), (3, 4)]

    for u, v in short_path_edges:
        G.add_edge(u, v, length=90)
        G.add_edge(v, u, length=90)
    for u, v in long_path_edges:
        G.add_edge(u, v, length=100)
        G.add_edge(v, u, length=100)
    return G


@pytest.fixture
def graph_with_busy_road():
    G = nx.MultiDiGraph()
    G.add_node(1, y=35.000, x=135.000)
    G.add_node(2, y=35.001, x=135.000)
    G.add_node(3, y=35.000, x=135.002)
    G.add_node(4, y=35.001, x=135.002)

    G.add_edge(1, 2, length=90, highway="primary")
    G.add_edge(2, 1, length=90, highway="primary")
    G.add_edge(2, 4, length=90, highway="primary")
    G.add_edge(4, 2, length=90, highway="primary")

    G.add_edge(1, 3, length=100, highway="residential")
    G.add_edge(3, 1, length=100, highway="residential")
    G.add_edge(3, 4, length=100, highway="residential")
    G.add_edge(4, 3, length=100, highway="residential")
    return G


class FakeScenicDataProvider:
    """Fake IScenicDataProvider with per-coordinate penalties, for controlled adapter testing."""
    def __init__(self, fixed_penalty=None, penalty_map=None):
        self.fixed_penalty = fixed_penalty
        self.penalty_map = penalty_map or {}

    def load(self, place):
        pass

    def get_scenic_penalty(self, lat, lon):
        key = (round(lat, 4), round(lon, 4))
        return self.penalty_map.get(key, self.fixed_penalty)


@pytest.mark.parametrize("orig,dest", [(1, 4), (2, 3), (1, 3), (2, 4)])
def test_heuristic_never_overestimates_actual_cost_via_networkx(simple_graph, orig, dest):
    scenic_provider = FakeScenicDataProvider(fixed_penalty=1.0)
    weight_fn = make_edge_weight_fn(simple_graph, scenic_provider)
    heuristic_fn = make_heuristic_fn(simple_graph)

    actual_path = nx.astar_path(simple_graph, orig, dest, heuristic=heuristic_fn, weight=weight_fn)
    actual_cost = sum(
        weight_fn(actual_path[i], actual_path[i + 1], simple_graph.edges[actual_path[i], actual_path[i + 1], 0])
        for i in range(len(actual_path) - 1)
    )
    heuristic_estimate = heuristic_fn(orig, dest)

    assert heuristic_estimate <= actual_cost


def test_scenic_route_produces_valid_connected_path(simple_graph):
    scenic_provider = FakeScenicDataProvider(fixed_penalty=BEST_CASE_SCENIC_PENALTY if False else 0.7)
    weight_fn = make_edge_weight_fn(simple_graph, scenic_provider)
    heuristic_fn = make_heuristic_fn(simple_graph)

    route = nx.astar_path(simple_graph, 1, 4, heuristic=heuristic_fn, weight=weight_fn)

    assert route[0] == 1
    assert route[-1] == 4
    assert len(route) >= 2


def test_scenic_route_diverges_from_shortest_path_when_incentivized(asymmetric_graph):
    baseline_route = nx.shortest_path(asymmetric_graph, 1, 4, weight="length")
    assert baseline_route == [1, 2, 4]

    node_2_mid = (round((35.000 + 35.001) / 2, 4), round((135.000 + 135.000) / 2, 4))
    node_3_mid = (round((35.000 + 35.001) / 2, 4), round((135.002 + 135.002) / 2, 4))

    scenic_provider = FakeScenicDataProvider(
        penalty_map={node_2_mid: 1.0, node_3_mid: 0.6},
        fixed_penalty=1.0,
    )
    weight_fn = make_edge_weight_fn(asymmetric_graph, scenic_provider)
    heuristic_fn = make_heuristic_fn(asymmetric_graph)

    scenic_route = nx.astar_path(asymmetric_graph, 1, 4, heuristic=heuristic_fn, weight=weight_fn)

    assert scenic_route == [1, 3, 4], f"Expected S-A* to prefer the scenic route via node 3, got {scenic_route}"


def test_scenic_route_avoids_busy_road_when_alternative_exists(graph_with_busy_road):
    scenic_provider = FakeScenicDataProvider(fixed_penalty=1.0)
    weight_fn = make_edge_weight_fn(graph_with_busy_road, scenic_provider)
    heuristic_fn = make_heuristic_fn(graph_with_busy_road)

    route = nx.astar_path(graph_with_busy_road, 1, 4, heuristic=heuristic_fn, weight=weight_fn)

    assert route == [1, 3, 4], f"Expected S-A* to avoid the primary road, got {route}"


# TODO(phase-3): add edge-case tests for disconnected graphs and single-node graphs.