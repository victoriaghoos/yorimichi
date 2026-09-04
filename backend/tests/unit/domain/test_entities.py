import dataclasses
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent / "scripts"))

import pytest

from yorimichi.domain.entities import Edge, Node, Route


def test_node_is_immutable():
    """Node is frozen — confirms accidental mutation is prevented."""
    node = Node(id="a", lat=35.0, lon=135.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        node.lat = 36.0


def test_edge_holds_node_references():
    node_a = Node(id="a", lat=35.000, lon=135.000)
    node_b = Node(id="b", lat=35.001, lon=135.000)
    edge = Edge(from_node=node_a, to_node=node_b, length=100)

    assert edge.from_node == node_a
    assert edge.to_node == node_b
    assert edge.highway_tag is None


def test_route_is_immutable():
    """Route is frozen — confirms accidental mutation is prevented."""
    route = Route(node_ids=("1", "2", "3"), length=150.5)
    with pytest.raises(dataclasses.FrozenInstanceError):
        route.length = 200.0


def test_route_holds_node_ids_and_length():
    route = Route(node_ids=("1", "2", "3"), length=150.5)

    assert route.node_ids == ("1", "2", "3")
    assert route.length == 150.5
    assert len(route.node_ids) == 3