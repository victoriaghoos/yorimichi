"""
Infrastructure adapter: concrete IScenicDataProvider implementation.
Wraps OSMnx feature-fetching and the KD-tree lookup, exposing only the
Domain-facing get_scenic_penalty() contract: no tree/weights ever leak out.

Caches loaded data per place, so repeated load() calls for the same place
(e.g. multiple route requests within one session) don't redundantly re-fetch
and re-index the same scenic data.
"""

import osmnx as ox
import numpy as np
from scipy.spatial import cKDTree

from yorimichi.domain.repositories import IScenicDataProvider
from yorimichi.domain.scoring import get_poi_weight, compute_scenic_penalty


class OSMnxScenicDataProvider(IScenicDataProvider):
    def __init__(self):
        self._tree = None
        self._weights = None
        self._loaded_key = None

    def load(self, place: str, categories: list[str] | None = None):
        active_categories = set(categories) if categories else None

        cache_key = (place, tuple(sorted(categories)) if categories else None)

        if cache_key == self._loaded_key:
            return

        tags = {
            "historic": True,
            "amenity": ["place_of_worship"],
            "leisure": ["park", "garden"],
            "tourism": ["attraction", "viewpoint"],
            "building": ["temple"],
            "natural": ["water", "wood"],
            "waterway": True,
        }
        scenic_gdf = ox.features_from_place(place, tags)

        projected = ox.projection.project_gdf(scenic_gdf)
        centroids_projected = projected.geometry.centroid
        centroids = centroids_projected.to_crs(scenic_gdf.crs)
        coords = np.array([[pt.y, pt.x] for pt in centroids])

        self._weights = np.array([
            get_poi_weight(row, active_categories) for _, row in scenic_gdf.iterrows()
        ])
        self._tree = cKDTree(coords)
        self._loaded_key = cache_key

    _call_count = 0

    def get_scenic_penalty(self, lat: float, lon: float) -> float:
        if self._tree is None:
            raise RuntimeError("load() must be called before get_scenic_penalty().")
        penalty = compute_scenic_penalty(lat, lon, self._tree, self._weights)
        return penalty