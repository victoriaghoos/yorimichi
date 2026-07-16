import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent / "scripts"))

import numpy as np
import pytest

from yorimichi.domain.scoring import (
    BEST_CASE_SCENIC_PENALTY,
    BUSY_ROAD_PENALTIES,
    DEFAULT_POI_WEIGHT,
    LIKELY_SCENIC_FALLBACK_WEIGHT,
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


def test_known_category_can_be_boosted():
    base_weight = get_poi_weight({"historic": "temple"})
    boosted_weight = get_poi_weight({"historic": "temple"}, {"shrines_temples": 1.5})

    assert boosted_weight == pytest.approx(base_weight * 1.5)


def test_non_boosted_category_stays_at_normal_strength():
    assert get_poi_weight({"leisure": "park"}, {"nature": 1.5}) == 0.6


def test_tree_is_weighted_as_nature_and_respects_boosts():
    assert get_poi_weight({"natural": "tree"}) == 0.5
    assert get_poi_weight({"natural": "tree"}, {"nature": 1.5}) == pytest.approx(0.75)


def test_nan_in_earlier_columns_does_not_block_later_tag_match():
    row = {
        "historic": float("nan"),
        "amenity": float("nan"),
        "leisure": float("nan"),
        "tourism": float("nan"),
        "building": float("nan"),
        "natural": "tree",
    }
    assert get_poi_weight(row) == 0.5


def test_nan_wikipedia_and_wikidata_do_not_trigger_historic_fallback():
    row = {"wikipedia": float("nan"), "wikidata": float("nan")}
    assert get_poi_weight(row) == DEFAULT_POI_WEIGHT


def test_tree_row_is_weighted_as_nature_and_respects_boosts():
    assert get_poi_weight({"natural": "tree_row"}) == pytest.approx(0.55)
    assert get_poi_weight({"natural": "tree_row"}, {"nature": 1.5}) == pytest.approx(0.825)


def test_landuse_forest_is_weighted_as_nature_and_respects_boosts():
    assert get_poi_weight({"landuse": "forest"}) == 0.6
    assert get_poi_weight({"landuse": "forest"}, {"nature": 1.5}) == pytest.approx(0.9)


def test_waterside_values_are_weighted_and_respect_boosts():
    assert get_poi_weight({"waterway": "river"}) == pytest.approx(0.85)
    assert get_poi_weight({"waterway": "canal"}) == pytest.approx(0.7)
    assert get_poi_weight({"waterway": "stream"}) == pytest.approx(0.65)
    assert get_poi_weight({"waterway": "river"}, {"waterside": 1.5}) == pytest.approx(1.275)


def test_ditch_is_not_treated_as_explicit_waterside():
    assert get_poi_weight({"waterway": "ditch"}) == DEFAULT_POI_WEIGHT


def test_cerasus_gets_priority_nature_weight_and_respects_boosts():
    assert get_poi_weight({"genus": "Cerasus"}) == 1.0
    assert get_poi_weight({"genus": "Cerasus"}, {"nature": 1.5}) == pytest.approx(1.5)


def test_torii_tags_get_priority_shrine_weight_and_respect_boosts():
    assert get_poi_weight({"ceremonial_gate": "torii"}) == 1.0
    assert get_poi_weight({"man_made": "ceremonial_gate"}, {"shrines_temples": 0.7}) == pytest.approx(0.7)


def test_likely_scenic_fallback_respects_category_boost():
    base_weight = get_poi_weight({"historic": "unknown_but_scenicish"})
    boosted_weight = get_poi_weight({"historic": "unknown_but_scenicish"}, {"historic_sites": 1.5})

    assert base_weight == LIKELY_SCENIC_FALLBACK_WEIGHT
    assert boosted_weight == pytest.approx(base_weight * 1.5)


def test_religious_fallback_respects_category_boost():
    base_weight = get_poi_weight({"religion": "shinto"})
    boosted_weight = get_poi_weight({"religion": "shinto"}, {"shrines_temples": 0.7})

    assert base_weight == 1.0
    assert boosted_weight == pytest.approx(0.7)


def test_wikipedia_fallback_respects_historic_sites_boost():
    assert get_poi_weight({"wikipedia": "ja:Some Landmark"}) == 0.9
    assert get_poi_weight({"wikipedia": "ja:Some Landmark"}, {"historic_sites": 1.5}) == pytest.approx(1.35)
    assert get_poi_weight({"wikidata": "Q123"}, {"historic_sites": 0.7}) == pytest.approx(0.63)


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