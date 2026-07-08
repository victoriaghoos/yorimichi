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
        self._loaded_place = None

    def load(self, place: str):
        if place == self._loaded_place:
            return  # already loaded for this place, skip redundant work

        tags = {
            "historic": True,
            "amenity": ["place_of_worship"],
            "leisure": ["park", "garden"],
            "tourism": ["attraction", "viewpoint"],
            "building": ["temple"],
        }
        scenic_gdf = ox.features_from_place(place, tags)
        print(f"Found {len(scenic_gdf)} scenic points")

        projected = ox.projection.project_gdf(scenic_gdf)
        centroids_projected = projected.geometry.centroid
        centroids = centroids_projected.to_crs(scenic_gdf.crs)
        coords = np.array([[pt.y, pt.x] for pt in centroids])

        self._weights = np.array([get_poi_weight(row) for _, row in scenic_gdf.iterrows()])
        self._tree = cKDTree(coords)
        self._loaded_place = place

    def get_scenic_penalty(self, lat: float, lon: float) -> float:
        if self._tree is None:
            raise RuntimeError("OSMnxScenicDataProvider.load() must be called before get_scenic_penalty()")
        return compute_scenic_penalty(lat, lon, self._tree, self._weights)