import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "scripts"))

import networkx as nx
import pytest
from prototype_route import (
    compute_scenic_penalty,
    make_edge_weight_fn,
    make_heuristic_fn,
    BEST_CASE_SCENIC_PENALTY,
)


@pytest.fixture
def simple_graph():
    """A small, bidirectional, hand-built graph so tests don't depend on network calls to OSM."""
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
    """
    A graph with two routes of different lengths between the same endpoints:
    1->2->4 is shorter (180m) than 1->3->4 (200m), so a plain shortest_path
    will always prefer 1->2->4 unless scenic incentive changes the outcome.
    """
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


@pytest.mark.parametrize("orig,dest", [(1, 4), (2, 3), (1, 3), (2, 4)])
def test_heuristic_never_overestimates_actual_cost(simple_graph, orig, dest):
    """
    Admissibility check: for any pair of nodes, the heuristic estimate must be
    less than or equal to the actual cheapest path cost found by A*.
    If this fails, A* is not guaranteed to find the true optimal scenic route.
    """
    tree = FakeTree(fixed_distance=0.01)  # far from scenic point
    weight_fn = make_edge_weight_fn(simple_graph, tree)
    heuristic_fn = make_heuristic_fn(simple_graph, best_case_penalty=BEST_CASE_SCENIC_PENALTY)

    actual_path = nx.astar_path(simple_graph, orig, dest, heuristic=heuristic_fn, weight=weight_fn)
    actual_cost = sum(
        weight_fn(actual_path[i], actual_path[i + 1], simple_graph.edges[actual_path[i], actual_path[i + 1], 0])
        for i in range(len(actual_path) - 1)
    )

    heuristic_estimate = heuristic_fn(orig, dest)

    assert heuristic_estimate <= actual_cost, (
        f"Heuristic ({heuristic_estimate}) overestimates actual cost ({actual_cost}): "
        "this breaks A*'s optimality guarantee."
    )


def test_scenic_route_produces_valid_connected_path(simple_graph):
    """
    Sanity check: with a meaningful scenic penalty in play, S-A* must still
    produce a valid, fully connected route from origin to destination.
    """
    tree = FakeTree(fixed_distance=0.0)  # very close to a scenic point
    weight_fn = make_edge_weight_fn(simple_graph, tree)
    heuristic_fn = make_heuristic_fn(simple_graph)

    route = nx.astar_path(simple_graph, 1, 4, heuristic=heuristic_fn, weight=weight_fn)

    assert route[0] == 1
    assert route[-1] == 4
    assert len(route) >= 2


def test_scenic_route_diverges_from_shortest_path_when_incentivized(asymmetric_graph):
    """
    When the physically longer route is scenic enough to become cheaper in
    scenic-weighted cost, S-A* should choose it over the shorter route that
    plain shortest_path always picks: proving the penalty mechanism actually
    changes routing decisions, not just that it runs without error.
    """
    baseline_route = nx.shortest_path(asymmetric_graph, 1, 4, weight="length")
    assert baseline_route == [1, 2, 4], "Baseline should always prefer the physically shorter route"

    # Make the midpoint of the long route (near node 3) very scenic (distance 0.0),
    # and the midpoint of the short route (near node 2) not scenic at all (distance far).
    node_2_mid = (round((35.000 + 35.001) / 2, 4), round((135.000 + 135.000) / 2, 4))
    node_3_mid = (round((35.000 + 35.001) / 2, 4), round((135.002 + 135.002) / 2, 4))

    distance_map = {
        node_2_mid: 0.01,  # far from scenic points -> no discount
        node_3_mid: 0.0,   # right next to a scenic point -> maximum discount
    }
    tree = FakeTree(distance_map=distance_map, fixed_distance=0.01)

    weight_fn = make_edge_weight_fn(asymmetric_graph, tree)
    heuristic_fn = make_heuristic_fn(asymmetric_graph)

    scenic_route = nx.astar_path(asymmetric_graph, 1, 4, heuristic=heuristic_fn, weight=weight_fn)

    assert scenic_route == [1, 3, 4], (
        f"Expected S-A* to prefer the scenic (longer) route via node 3, got {scenic_route}"
    )


def test_scenic_penalty_decreases_with_proximity():
    """Points closer to scenic locations should get a lower (more favorable) penalty factor."""
    close_tree = FakeTree(fixed_distance=0.0)
    far_tree = FakeTree(fixed_distance=0.01)

    close_penalty = compute_scenic_penalty(35.0, 135.0, close_tree)
    far_penalty = compute_scenic_penalty(35.0, 135.0, far_tree)

    assert close_penalty < far_penalty


def test_scenic_penalty_stays_within_expected_bounds():
    close_tree = FakeTree(fixed_distance=0.0)
    far_tree = FakeTree(fixed_distance=1.0)

    close_penalty = compute_scenic_penalty(35.0, 135.0, close_tree)
    far_penalty = compute_scenic_penalty(35.0, 135.0, far_tree)

    assert BEST_CASE_SCENIC_PENALTY <= close_penalty <= 1.0
    assert BEST_CASE_SCENIC_PENALTY <= far_penalty <= 1.0


# TODO(phase-1.5): add edge-case tests for orig==dest, disconnected graphs, and empty scenic datasets.