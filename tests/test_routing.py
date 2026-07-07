import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "scripts"))

from yorimichi.domain.routing import haversine_distance


def test_haversine_matches_known_distance():
    """
    Sanity check: Haversine (straight-line) distance between Kiyomizu-dera and
    Yasaka Shrine should be somewhat LESS than the ~1446.9m actual walking route
    (straight-line distance is always <= real path distance), but still in a
    plausible range for two points known to be roughly 1-1.5km apart.
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