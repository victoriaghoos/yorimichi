"""
Infrastructure adapter: concrete IScenicDataProvider implementation.
Wraps OSMnx feature-fetching and the KD-tree lookup, exposing only the
Domain-facing get_scenic_penalty() contract: no tree/weights ever leak out.

Caches loaded data per route corridor (bbox) + category boosts, so repeated
load() calls for the same request area don't redundantly re-fetch and
re-index scenic data.
"""

import math
import threading
from dataclasses import dataclass
import pandas as pd
import osmnx as ox
import numpy as np
from scipy.spatial import cKDTree

from yorimichi.domain.repositories import IScenicDataProvider, IScenicIndex
from yorimichi.domain.scoring import get_poi_weight, compute_scenic_penalty


@dataclass(frozen=True)
class ScenicIndex(IScenicIndex):
    _tree: cKDTree
    _weights: np.ndarray

    def get_scenic_penalty(self, lat: float, lon: float) -> float:
        return compute_scenic_penalty(lat, lon, self._tree, self._weights)


class OSMnxScenicDataProvider(IScenicDataProvider):
    _SCENIC_MARGIN_METERS = 1500.0

    def __init__(self):
        self._cache: dict[tuple[str, tuple[tuple[str, float], ...] | None], ScenicIndex] = {}
        self._cache_lock = threading.Lock()

    def load(
        self,
        orig_point: tuple[float, float],
        dest_point: tuple[float, float],
        category_boosts: dict[str, float] | None = None,
    ) -> IScenicIndex:
        min_lat, min_lon, max_lat, max_lon = self._compute_bbox(orig_point, dest_point)
        bbox = (min_lon, min_lat, max_lon, max_lat)
        cache_key = (
            f"{min_lat:.6f}|{min_lon:.6f}|{max_lat:.6f}|{max_lon:.6f}",
            tuple(sorted(category_boosts.items())) if category_boosts else None,
        )

        with self._cache_lock:
            cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        tags = {
            "historic": True,
            "amenity": ["place_of_worship"],
            "leisure": ["park", "garden"],
            "tourism": ["attraction", "viewpoint"],
            "building": ["temple"],
            "natural": ["water", "wood", "tree", "tree_row"],
            "landuse": ["forest"],
            "waterway": True,
            "genus": ["Cerasus"],
            "ceremonial_gate": ["torii"],
            "man_made": ["ceremonial_gate"],
        }
        scenic_gdf = ox.features_from_bbox(bbox, tags=tags)

        if scenic_gdf.empty:
            index = ScenicIndex(cKDTree(np.array([[0.0, 0.0]])), np.array([0.0]))
            with self._cache_lock:
                self._cache.setdefault(cache_key, index)
                index = self._cache[cache_key]
            return index

        projected = ox.projection.project_gdf(scenic_gdf)
        centroids_projected = projected.geometry.centroid
        centroids = centroids_projected.to_crs(scenic_gdf.crs)
        coords = np.array([[pt.y, pt.x] for pt in centroids])

        weights = np.array([
            get_poi_weight({k: v for k, v in row.items() if pd.notna(v)}, category_boosts)
            for _, row in scenic_gdf.iterrows()
        ])
        index = ScenicIndex(cKDTree(coords), weights)
        with self._cache_lock:
            self._cache.setdefault(cache_key, index)
            return self._cache[cache_key]

    def _compute_bbox(
        self,
        orig_point: tuple[float, float],
        dest_point: tuple[float, float],
    ) -> tuple[float, float, float, float]:
        orig_lat, orig_lon = orig_point
        dest_lat, dest_lon = dest_point

        center_lat = (orig_lat + dest_lat) / 2.0
        lat_margin = self._SCENIC_MARGIN_METERS / 111_320.0
        lon_denominator = max(111_320.0 * abs(math.cos(math.radians(center_lat))), 1.0)
        lon_margin = self._SCENIC_MARGIN_METERS / lon_denominator

        min_lat = min(orig_lat, dest_lat) - lat_margin
        max_lat = max(orig_lat, dest_lat) + lat_margin
        min_lon = min(orig_lon, dest_lon) - lon_margin
        max_lon = max(orig_lon, dest_lon) + lon_margin
        return min_lat, min_lon, max_lat, max_lon
