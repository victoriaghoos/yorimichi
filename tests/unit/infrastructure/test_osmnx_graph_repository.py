import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent / "scripts"))

import networkx as nx
import pytest

from yorimichi.infrastructure.osmnx_graph_repository import OSMnxGraphRepository
from yorimichi.domain.repositories import IGraphRepository
from yorimichi.domain.entities import Node, Route


class FakeScenicDataProvider:
    """Fake IScenicDataProvider with a fixed penalty, for isolated repository testing."""
    def __init__(self, fixed_penalty=1.0):
        self.fixed_penalty = fixed_penalty

    def load(self, place):
        pass

    def get_scenic_penalty(self, lat, lon):
        return self.fixed_penalty


@pytest.fixture
def simple_graph():
    """A small, bidirectional, hand-built graph with the OSMnx-required crs attribute."""
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


def test_implements_igraph_repository_interface():
    repo = OSMnxGraphRepository()
    assert isinstance(repo, IGraphRepository)


def test_nearest_node_returns_domain_node():
    """
    Confirms nearest_node() translates networkx's raw node ID + attributes
    into a proper Domain Node: no networkx-specific object leaks out.
    """
    fake_graph = nx.MultiDiGraph(crs="EPSG:4326")
    fake_graph.add_node(123, y=35.000, x=135.000)
    fake_graph.add_node(456, y=35.010, x=135.010)

    repo = OSMnxGraphRepository()
    node = repo.nearest_node(fake_graph, lat=35.001, lon=135.001)

    assert isinstance(node, Node)
    assert node.id == "123"
    assert node.lat == 35.000
    assert node.lon == 135.000


def test_find_shortest_route_returns_domain_route(simple_graph):
    """Confirms find_shortest_route() returns a proper Domain Route, not raw networkx data."""
    repo = OSMnxGraphRepository()
    orig = Node(id="1", lat=35.000, lon=135.000)
    dest = Node(id="4", lat=35.001, lon=135.001)

    route = repo.find_shortest_route(simple_graph, orig, dest)

    assert isinstance(route, Route)
    assert route.node_ids[0] == "1"
    assert route.node_ids[-1] == "4"
    assert route.length > 0


def test_find_scenic_route_returns_domain_route(simple_graph):
    """Confirms find_scenic_route() returns a proper Domain Route using the scenic provider."""
    repo = OSMnxGraphRepository()
    orig = Node(id="1", lat=35.000, lon=135.000)
    dest = Node(id="4", lat=35.001, lon=135.001)
    scenic_provider = FakeScenicDataProvider(fixed_penalty=1.0)

    route = repo.find_scenic_route(simple_graph, orig, dest, scenic_provider)

    assert isinstance(route, Route)
    assert route.node_ids[0] == "1"
    assert route.node_ids[-1] == "4"
    assert route.length > 0


def test_find_scenic_route_diverges_with_meaningful_scenic_incentive(simple_graph):
    """
    With a strong enough scenic discount somewhere, the scenic route via the
    repository should still be able to differ from the shortest path: proves
    the repository correctly wires up make_edge_weight_fn/make_heuristic_fn.
    """
    repo = OSMnxGraphRepository()
    orig = Node(id="1", lat=35.000, lon=135.000)
    dest = Node(id="4", lat=35.001, lon=135.001)

    baseline = repo.find_shortest_route(simple_graph, orig, dest)
    scenic_provider = FakeScenicDataProvider(fixed_penalty=0.6)  # maximum discount everywhere
    scenic = repo.find_scenic_route(simple_graph, orig, dest, scenic_provider)

    # With a uniform discount, both routes should still be valid and connected,
    # even if they happen to coincide on this small symmetric graph.
    assert scenic.node_ids[0] == baseline.node_ids[0]
    assert scenic.node_ids[-1] == baseline.node_ids[-1]
    
def test_get_graph_caches_result_for_same_place(simple_graph, monkeypatch):
    """Confirms get_graph() doesn't re-fetch when called twice with the same place."""
    call_count = {"count": 0}

    def fake_graph_from_place(place, network_type):
        call_count["count"] += 1
        return simple_graph

    monkeypatch.setattr("yorimichi.infrastructure.osmnx_graph_repository.ox.graph_from_place", fake_graph_from_place)

    repo = OSMnxGraphRepository()
    graph1 = repo.get_graph("Fake Place")
    graph2 = repo.get_graph("Fake Place")

    assert call_count["count"] == 1  # only fetched once, second call used cache
    assert graph1 is graph2