import pytest
import pandas as pd

from yorimichi.infrastructure.osmnx_scenic_data_provider import OSMnxScenicDataProvider


def test_load_returns_scenic_index_with_penalty_lookup(monkeypatch):
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

    monkeypatch.setattr("yorimichi.infrastructure.osmnx_scenic_data_provider.ox.features_from_bbox", lambda bbox, tags: scenic_gdf)
    monkeypatch.setattr(
        "yorimichi.infrastructure.osmnx_scenic_data_provider.ox.projection.project_gdf",
        lambda gdf: FakeProjectedGdf(FakeGeometrySeries()),
    )
    monkeypatch.setattr("yorimichi.infrastructure.osmnx_scenic_data_provider.cKDTree", FakeTree)

    provider = OSMnxScenicDataProvider()
    scenic_index = provider.load((35.0, 135.0), (35.001, 135.001))

    assert scenic_index.get_scenic_penalty(35.0, 135.0) < 1.0


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

    def fake_features_from_bbox(bbox, tags):
        captured["bbox"] = bbox
        captured["tags"] = tags
        return scenic_gdf

    monkeypatch.setattr("yorimichi.infrastructure.osmnx_scenic_data_provider.ox.features_from_bbox", fake_features_from_bbox)
    monkeypatch.setattr(
        "yorimichi.infrastructure.osmnx_scenic_data_provider.ox.projection.project_gdf",
        lambda gdf: FakeProjectedGdf(FakeGeometrySeries()),
    )
    monkeypatch.setattr("yorimichi.infrastructure.osmnx_scenic_data_provider.cKDTree", FakeTree)

    provider = OSMnxScenicDataProvider()
    scenic_index = provider.load((35.0, 135.0), (35.001, 135.001))

    assert "bbox" in captured
    assert captured["tags"]["natural"] == ["water", "wood", "tree", "tree_row"]
    assert captured["tags"]["landuse"] == ["forest"]
    assert captured["tags"]["genus"] == ["Cerasus"]
    assert captured["tags"]["ceremonial_gate"] == ["torii"]
    assert captured["tags"]["man_made"] == ["ceremonial_gate"]
    assert scenic_index.get_scenic_penalty(35.0, 135.0) < 1.0


def test_load_reuses_cached_immutable_index_for_same_key(monkeypatch):
    call_count = {"features": 0}

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

    def fake_features_from_bbox(bbox, tags):
        call_count["features"] += 1
        return scenic_gdf

    monkeypatch.setattr("yorimichi.infrastructure.osmnx_scenic_data_provider.ox.features_from_bbox", fake_features_from_bbox)
    monkeypatch.setattr(
        "yorimichi.infrastructure.osmnx_scenic_data_provider.ox.projection.project_gdf",
        lambda gdf: FakeProjectedGdf(FakeGeometrySeries()),
    )
    monkeypatch.setattr("yorimichi.infrastructure.osmnx_scenic_data_provider.cKDTree", FakeTree)

    provider = OSMnxScenicDataProvider()
    index_1 = provider.load((35.0, 135.0), (35.001, 135.001), {"nature": 1.5})
    index_2 = provider.load((35.0, 135.0), (35.001, 135.001), {"nature": 1.5})

    assert call_count["features"] == 1
    assert index_1 is index_2