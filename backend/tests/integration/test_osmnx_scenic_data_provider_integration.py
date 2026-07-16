"""
Integration test: verifies OSMnxScenicDataProvider against REAL OpenStreetMap
data via a live network call to the Overpass API. This is intentionally
separate from tests/unit/, which uses fakes/mocks exclusively for speed and
network independence.

This test is slow (real network I/O, ~seconds) and requires internet access.
Run it deliberately, e.g.:
    poetry run pytest tests/integration/ -v
rather than as part of routine fast unit-test iteration.
"""

import pytest

from yorimichi.infrastructure.osmnx_scenic_data_provider import OSMnxScenicDataProvider
from yorimichi.domain.scoring import BEST_CASE_SCENIC_PENALTY

# Real, known coordinates from manual verification in this project:
# Kiyomizu-dera (near many temples/shrines: should score close to maximum discount)
NEAR_TEMPLE_LAT, NEAR_TEMPLE_LON = 34.9949, 135.7850
DEST_LAT, DEST_LON = 35.0038, 135.7788

# A coordinate far outside Higashiyama entirely, to sanity-check the provider
# doesn't silently return a nonsensical penalty for out-of-area points.
FAR_AWAY_LAT, FAR_AWAY_LON = 0.0, 0.0


@pytest.mark.integration
def test_load_fetches_real_scenic_points_for_higashiyama():
    """Confirms load() successfully fetches real OSM data without errors."""
    provider = OSMnxScenicDataProvider()
    scenic_index = provider.load((NEAR_TEMPLE_LAT, NEAR_TEMPLE_LON), (DEST_LAT, DEST_LON))

    penalty = scenic_index.get_scenic_penalty(NEAR_TEMPLE_LAT, NEAR_TEMPLE_LON)
    assert BEST_CASE_SCENIC_PENALTY <= penalty <= 1.0


@pytest.mark.integration
def test_get_scenic_penalty_near_kiyomizu_dera_reflects_high_scenic_density():
    """
    Confirms a coordinate known to be near a dense cluster of temples/shrines
    (validated manually earlier in this project via main.py) receives a
    meaningfully discounted scenic penalty, not a neutral 1.0.
    """
    provider = OSMnxScenicDataProvider()
    scenic_index = provider.load((NEAR_TEMPLE_LAT, NEAR_TEMPLE_LON), (DEST_LAT, DEST_LON))

    penalty = scenic_index.get_scenic_penalty(NEAR_TEMPLE_LAT, NEAR_TEMPLE_LON)

    assert BEST_CASE_SCENIC_PENALTY <= penalty <= 1.0
    assert penalty < 1.0, "Expected some scenic discount near Kiyomizu-dera, got a fully neutral penalty"


@pytest.mark.integration
def test_get_scenic_penalty_stays_within_valid_bounds_for_distant_coordinates():
    """
    Even for a coordinate far outside Higashiyama, get_scenic_penalty() should
    still return a value within the valid [BEST_CASE_SCENIC_PENALTY, 1.0] range:
    it should never crash or return an out-of-bounds number, since the KD-tree
    always returns *a* nearest point, however far away.
    """
    provider = OSMnxScenicDataProvider()
    scenic_index = provider.load((NEAR_TEMPLE_LAT, NEAR_TEMPLE_LON), (DEST_LAT, DEST_LON))

    penalty = scenic_index.get_scenic_penalty(FAR_AWAY_LAT, FAR_AWAY_LON)

    assert BEST_CASE_SCENIC_PENALTY <= penalty <= 1.0
    assert penalty == 1.0, "A coordinate this far from any scenic point should receive no discount at all"