import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent / "scripts"))

import numpy as np
import pytest

from yorimichi.domain.scoring import (
    BEST_CASE_SCENIC_PENALTY,
    BUSY_ROAD_PENALTIES,
    DEFAULT_POI_WEIGHT,
    compute_scenic_penalty,
    get_poi_weight,
    get_road_penalty,
)


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


def test_scenic_penalty_decreases_with_proximity():
    """Points closer to scenic locations should get a lower (more favorable) penalty factor."""
    close_tree = FakeTree(fixed_distance=0.0)
    far_tree = FakeTree(fixed_distance=0.01)
    weights = np.array([1.0])

    close_penalty = compute_scenic_penalty(35.0, 135.0, close_tree, weights)
    far_penalty = compute_scenic_penalty(35.0, 135.0, far_tree, weights)

    assert close_penalty < far_penalty


def test_scenic_penalty_stays_within_expected_bounds():
    close_tree = FakeTree(fixed_distance=0.0)
    far_tree = FakeTree(fixed_distance=1.0)
    weights = np.array([1.0])

    close_penalty = compute_scenic_penalty(35.0, 135.0, close_tree, weights)
    far_penalty = compute_scenic_penalty(35.0, 135.0, far_tree, weights)

    assert BEST_CASE_SCENIC_PENALTY <= close_penalty <= 1.0
    assert BEST_CASE_SCENIC_PENALTY <= far_penalty <= 1.0


def test_higher_weight_poi_gets_stronger_discount_at_same_distance():
    """A higher POI weight (e.g., temple) should yield a lower penalty than attraction at equal distance."""
    tree = FakeTree(fixed_distance=0.001)

    temple_weight = get_poi_weight({"historic": "temple"})
    attraction_weight = get_poi_weight({"tourism": "attraction"})

    temple_penalty = compute_scenic_penalty(35.0, 135.0, tree, np.array([temple_weight]))
    attraction_penalty = compute_scenic_penalty(35.0, 135.0, tree, np.array([attraction_weight]))

    assert temple_weight > attraction_weight
    assert temple_penalty < attraction_penalty


def test_new_historic_categories_have_expected_weights():
    """
    Sanity check for the broadened POI_TYPE_WEIGHTS table added in Phase 2.5,
    when `historic` started being queried broadly (True) instead of a fixed list.
    """
    assert get_poi_weight({"historic": "castle"}) == 0.9
    assert get_poi_weight({"historic": "memorial"}) == 0.65
    assert get_poi_weight({"historic": "tunnel"}) == DEFAULT_POI_WEIGHT
    assert get_poi_weight({"historic": "substation"}) == DEFAULT_POI_WEIGHT


def test_busy_road_increases_edge_cost():
    """A busy road (e.g. primary) should cost more than a neutral road at the same length."""
    neutral_edge = {"length": 100}
    busy_edge = {"length": 100, "highway": "primary"}

    assert get_road_penalty(neutral_edge) == 1.0
    assert get_road_penalty(busy_edge) > 1.0


def test_busy_road_penalty_uses_worst_case_for_multiple_tags():
    """When an edge has multiple highway tags, the most severe penalty should apply."""
    mixed_edge = {"length": 100, "highway": ["residential", "trunk"]}
    assert get_road_penalty(mixed_edge) == BUSY_ROAD_PENALTIES["trunk"]


# TODO(phase-3): add edge-case tests for empty scenic datasets.