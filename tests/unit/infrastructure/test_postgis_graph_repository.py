import networkx as nx
import pytest

from yorimichi.domain.entities import Node, Route
from yorimichi.infrastructure.postgis_graph_repository import PostGISGraphRepository


class FakeScenicDataProvider:
    def __init__(self, fixed_penalty=1.0):
        self.fixed_penalty = fixed_penalty

    def load(self, place):
        pass

    def get_scenic_penalty(self, lat, lon):
        return self.fixed_penalty


@pytest.fixture
def simple_graph():
    """
    Note: PostGIS-sourced graphs use STRING node IDs (unlike OSMnx's
    integer IDs), since yorimichi_nodes.id is a String column.
    """
    G = nx.MultiDiGraph(crs="EPSG:4326")
    G.add_node("1", y=35.000, x=135.000)
    G.add_node("2", y=35.001, x=135.000)
    G.add_node("3", y=35.000, x=135.001)
    G.add_node("4", y=35.001, x=135.001)

    edges = [("1", "2"), ("2", "4"), ("1", "3"), ("3", "4")]
    for u, v in edges:
        G.add_edge(u, v, length=100)
        G.add_edge(v, u, length=100)
    return G


@pytest.fixture
def repo():
    return PostGISGraphRepository("postgresql://placeholder/placeholder")


def test_find_shortest_route_returns_domain_route(repo, simple_graph):
    orig = Node(id="1", lat=35.000, lon=135.000)
    dest = Node(id="4", lat=35.001, lon=135.001)

    route = repo.find_shortest_route(simple_graph, orig, dest)

    assert isinstance(route, Route)
    assert route.node_ids[0] == "1"
    assert route.node_ids[-1] == "4"
    assert route.length > 0


def test_find_scenic_route_returns_domain_route(repo, simple_graph):
    orig = Node(id="1", lat=35.000, lon=135.000)
    dest = Node(id="4", lat=35.001, lon=135.001)
    scenic_provider = FakeScenicDataProvider(fixed_penalty=0.6)

    route = repo.find_scenic_route(simple_graph, orig, dest, scenic_provider)

    assert isinstance(route, Route)
    assert route.node_ids[0] == "1"
    assert route.node_ids[-1] == "4"
    assert route.length > 0