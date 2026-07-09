import pytest
import pandas as pd

from yorimichi.infrastructure.osmnx_scenic_data_provider import OSMnxScenicDataProvider


def test_get_scenic_penalty_raises_if_not_loaded():
    """
    Confirms the defensive check: calling get_scenic_penalty() before load()
    fails loudly and clearly, rather than crashing on a None tree with a
    confusing AttributeError.
    """
    provider = OSMnxScenicDataProvider()

    with pytest.raises(RuntimeError, match="load\\(\\) must be called"):
        provider.get_scenic_penalty(35.0, 135.0)


def test_implements_iscenic_data_provider_interface():
    """Sanity check: OSMnxScenicDataProvider actually satisfies the Domain contract."""
    from yorimichi.domain.repositories import IScenicDataProvider

    provider = OSMnxScenicDataProvider()
    assert isinstance(provider, IScenicDataProvider)


def test_load_requests_expected_scenic_feature_tags(monkeypatch):
    captured = {}

    class FakeProjectedGdf:
        def __init__(self, geometry):
            self.geometry = geometry

    class FakeCentroids:
        def __init__(self, coords):
            self._coords = coords

        def to_crs(self, crs):
            return [type("Point", (), {"y": lat, "x": lon})() for lat, lon in self._coords]

    class FakeGeometrySeries:
        @property
        def centroid(self):
            return FakeCentroids([(35.0, 135.0)])

    class FakeTree:
        def __init__(self, coords):
            self.coords = coords

        def query(self, point):
            return 0.0, 0

    scenic_gdf = pd.DataFrame([{"natural": "tree"}])
    scenic_gdf.crs = "EPSG:4326"

    def fake_features_from_place(place, tags):
        captured["place"] = place
        captured["tags"] = tags
        return scenic_gdf

    monkeypatch.setattr("yorimichi.infrastructure.osmnx_scenic_data_provider.ox.features_from_place", fake_features_from_place)
    monkeypatch.setattr(
        "yorimichi.infrastructure.osmnx_scenic_data_provider.ox.projection.project_gdf",
        lambda gdf: FakeProjectedGdf(FakeGeometrySeries()),
    )
    monkeypatch.setattr("yorimichi.infrastructure.osmnx_scenic_data_provider.cKDTree", FakeTree)

    provider = OSMnxScenicDataProvider()
    provider.load("Fake Place")

    assert captured["place"] == "Fake Place"
    assert captured["tags"]["natural"] == ["water", "wood", "tree", "tree_row"]
    assert captured["tags"]["landuse"] == ["forest"]
    assert captured["tags"]["genus"] == ["Cerasus"]
    assert captured["tags"]["ceremonial_gate"] == ["torii"]
    assert captured["tags"]["man_made"] == ["ceremonial_gate"]