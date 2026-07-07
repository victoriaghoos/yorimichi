import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent / "scripts"))

from yorimichi.domain.entities import Node, Edge
from yorimichi.domain.routing import (
    calculate_edge_cost,
    calculate_heuristic,
    haversine_distance,
)
from yorimichi.domain.scoring import BEST_CASE_SCENIC_PENALTY


class FakeScenicDataProvider:
    """Fake IScenicDataProvider for isolated Domain testing: no KD-tree, no real data."""
    def __init__(self, fixed_penalty=1.0):
        self.fixed_penalty = fixed_penalty

    def load(self, place):
        pass

    def get_scenic_penalty(self, lat, lon):
        return self.fixed_penalty


def test_haversine_matches_known_distance():
    """
    Sanity check: straight-line distance between Kiyomizu-dera and Yasaka Shrine
    should be somewhat LESS than the ~1446.9m actual walking route.
    """
    dist = haversine_distance(34.9949, 135.7850, 35.0038, 135.7788)
    assert 900 < dist < 1450


def test_haversine_zero_distance_for_same_point():
    dist = haversine_distance(35.0, 135.0, 35.0, 135.0)
    assert dist == 0


def test_haversine_symmetric():
    dist_ab = haversine_distance(34.9949, 135.7850, 35.0038, 135.7788)
    dist_ba = haversine_distance(35.0038, 135.7788, 34.9949, 135.7850)
    assert abs(dist_ab - dist_ba) < 0.001


def test_calculate_edge_cost_uses_only_domain_entities():
    """
    Confirms calculate_edge_cost works purely off Node/Edge entities and an
    IScenicDataProvider — no networkx, no KD-tree, proof of Domain isolation.
    """
    node_a = Node(id="a", lat=35.000, lon=135.000)
    node_b = Node(id="b", lat=35.001, lon=135.000)
    edge = Edge(from_node=node_a, to_node=node_b, length=100, highway_tag="primary")

    scenic_provider = FakeScenicDataProvider(fixed_penalty=1.0)

    cost = calculate_edge_cost(edge, scenic_provider)
    assert cost > 100  # primary road penalty should push cost above raw length


def test_calculate_edge_cost_applies_scenic_discount():
    node_a = Node(id="a", lat=35.000, lon=135.000)
    node_b = Node(id="b", lat=35.001, lon=135.000)
    edge = Edge(from_node=node_a, to_node=node_b, length=100, highway_tag=None)

    scenic_provider = FakeScenicDataProvider(fixed_penalty=BEST_CASE_SCENIC_PENALTY)

    cost = calculate_edge_cost(edge, scenic_provider)
    assert cost < 100


def test_heuristic_never_overestimates_actual_cost():
    """
    Admissibility check: the heuristic estimate must never exceed the actual
    cost of a direct edge at maximum scenic discount and no road penalty.
    """
    node_a = Node(id="a", lat=35.000, lon=135.000)
    node_b = Node(id="b", lat=35.001, lon=135.000)

    heuristic_estimate = calculate_heuristic(node_a, node_b)

    edge = Edge(
        from_node=node_a, to_node=node_b,
        length=haversine_distance(35.000, 135.000, 35.001, 135.000),
        highway_tag=None,
    )
    scenic_provider = FakeScenicDataProvider(fixed_penalty=BEST_CASE_SCENIC_PENALTY)
    best_case_actual_cost = calculate_edge_cost(edge, scenic_provider)

    assert heuristic_estimate <= best_case_actual_cost + 1e-6


def test_heuristic_uses_best_case_scenic_penalty_by_default():
    node_a = Node(id="a", lat=35.000, lon=135.000)
    node_b = Node(id="b", lat=35.001, lon=135.000)

    expected = haversine_distance(35.000, 135.000, 35.001, 135.000) * BEST_CASE_SCENIC_PENALTY
    actual = calculate_heuristic(node_a, node_b)

    assert abs(expected - actual) < 1e-6


# TODO(phase-3): add edge-case tests for zero-length edges and identical from/to nodes.