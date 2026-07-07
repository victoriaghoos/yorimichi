import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent / "scripts"))

import networkx as nx

from yorimichi.infrastructure.osmnx_graph_repository import OSMnxGraphRepository
from yorimichi.domain.repositories import IGraphRepository
from yorimichi.domain.entities import Node


def test_implements_igraph_repository_interface():
    repo = OSMnxGraphRepository()
    assert isinstance(repo, IGraphRepository)


def test_nearest_node_returns_domain_node():
    """
    Confirms nearest_node() translates networkx's raw node ID + attributes
    into a proper Domain Node — no networkx-specific object leaks out.
    """
    fake_graph = nx.MultiDiGraph(crs="EPSG:4326")  # OSMnx requires this graph-level attribute
    fake_graph.add_node(123, y=35.000, x=135.000)
    fake_graph.add_node(456, y=35.010, x=135.010)

    repo = OSMnxGraphRepository()
    node = repo.nearest_node(fake_graph, lat=35.001, lon=135.001)

    assert isinstance(node, Node)
    assert node.id == "123"
    assert node.lat == 35.000
    assert node.lon == 135.000