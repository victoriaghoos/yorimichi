import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent / "scripts"))

import numpy as np
import pytest

from yorimichi.domain.entities import Node, Edge
from yorimichi.domain.routing import (
    calculate_edge_cost,
    calculate_heuristic,
    haversine_distance,
)
from yorimichi.domain.scoring import BEST_CASE_SCENIC_PENALTY


class FakeTree:
    """Fake KD-tree with per-coordinate distances, so scenic proximity can be controlled per test."""
    def __init__(self, fixed_distance=None, distance_map=None):
        self.fixed_distance = fixed_distance
        self.distance_map = distance_map or {}

    def query(self, point):
        key = (round(point[0], 4), round(point[1], 4))
        if key in self.distance_map:
            return self.distance_map[key], 0
        return self.fixed_distance, 0


def test_haversine_matches_known_distance():
    """
    Sanity check: straight-line distance between Kiyomizu-dera and Yasaka Shrine
    should be somewhat LESS than the ~1446.9m actual walking route (straight-line
    distance is always <= real path distance), but still in a plausible range.
    """
    dist = haversine_distance(34.9949, 135.7850, 35.0038, 135.7788)
    assert 900 < dist < 1450


def test_haversine_zero_distance_for_same_point():
    """Distance from a point to itself should be exactly zero."""
    dist = haversine_distance(35.0, 135.0, 35.0, 135.0)
    assert dist == 0


def test_haversine_symmetric():
    """Distance from A to B should equal distance from B to A."""
    dist_ab = haversine_distance(34.9949, 135.7850, 35.0038, 135.7788)
    dist_ba = haversine_distance(35.0038, 135.7788, 34.9949, 135.7850)
    assert abs(dist_ab - dist_ba) < 0.001


def test_calculate_edge_cost_uses_only_domain_entities():
    """
    Confirms calculate_edge_cost works purely off Node/Edge entities: no
    networkx graph, no (u, v, data) tuple — proof the Domain layer has no
    leaked infrastructure dependency.
    """
    node_a = Node(id="a", lat=35.000, lon=135.000)
    node_b = Node(id="b", lat=35.001, lon=135.000)
    edge = Edge(from_node=node_a, to_node=node_b, length=100, highway_tag="primary")

    tree = FakeTree(fixed_distance=0.01)
    weights = np.array([1.0])

    cost = calculate_edge_cost(edge, tree, weights)
    assert cost > 100  # primary road penalty should push cost above raw length


def test_calculate_edge_cost_applies_scenic_discount():
    """A scenic-proximate edge should cost less than its raw length."""
    node_a = Node(id="a", lat=35.000, lon=135.000)
    node_b = Node(id="b", lat=35.001, lon=135.000)
    edge = Edge(from_node=node_a, to_node=node_b, length=100, highway_tag=None)

    tree = FakeTree(fixed_distance=0.0)  # right next to a scenic point
    weights = np.array([1.0])

    cost = calculate_edge_cost(edge, tree, weights)
    assert cost < 100


def test_heuristic_never_overestimates_actual_cost():
    """
    Admissibility check, pure Domain version: the heuristic estimate between
    two nodes must never exceed the actual cost of a single direct edge
    between them at maximum scenic discount and no road penalty — the
    best-case scenario the heuristic assumes.
    """
    node_a = Node(id="a", lat=35.000, lon=135.000)
    node_b = Node(id="b", lat=35.001, lon=135.000)

    heuristic_estimate = calculate_heuristic(node_a, node_b)

    edge = Edge(from_node=node_a, to_node=node_b, length=haversine_distance(35.000, 135.000, 35.001, 135.000), highway_tag=None)
    tree = FakeTree(fixed_distance=0.0)  # maximum scenic discount: the best case
    weights = np.array([1.0])
    best_case_actual_cost = calculate_edge_cost(edge, tree, weights)

    assert heuristic_estimate <= best_case_actual_cost + 1e-6  # small tolerance for floating point


def test_heuristic_uses_best_case_scenic_penalty_by_default():
    """Confirms the heuristic's default scaling factor matches BEST_CASE_SCENIC_PENALTY."""
    node_a = Node(id="a", lat=35.000, lon=135.000)
    node_b = Node(id="b", lat=35.001, lon=135.000)

    expected = haversine_distance(35.000, 135.000, 35.001, 135.000) * BEST_CASE_SCENIC_PENALTY
    actual = calculate_heuristic(node_a, node_b)

    assert abs(expected - actual) < 1e-6


# TODO(phase-3): add edge-case tests for zero-length edges and identical from/to nodes.