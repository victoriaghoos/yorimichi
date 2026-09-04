"""
Infrastructure adapter: concrete IGraphRepository implementation.
Owns all networkx-specific routing execution (shortest_path, astar_path).

Caches loaded graphs per route corridor (origin/destination bbox), so repeated
queries for the same area don't redundantly re-fetch and re-parse the same
graph data.
"""

import math

import networkx as nx
import osmnx as ox

from yorimichi.domain.entities import Node, Route
from yorimichi.domain.repositories import IGraphRepository
from yorimichi.infrastructure.osmnx_routing_adapter import make_edge_weight_fn, make_heuristic_fn


class OSMnxGraphRepository(IGraphRepository):
    _SUBGRAPH_MARGIN_METERS = 1500.0

    def __init__(self):
        self._cached_graphs = {}

    def get_graph(
        self,
        orig_point: tuple[float, float],
        dest_point: tuple[float, float],
    ):
        min_lat, min_lon, max_lat, max_lon = self._compute_bbox(orig_point, dest_point)
        bbox = (min_lon, min_lat, max_lon, max_lat)
        cache_key = f"{min_lat:.6f}|{min_lon:.6f}|{max_lat:.6f}|{max_lon:.6f}"
        if cache_key not in self._cached_graphs:
            self._cached_graphs[cache_key] = ox.graph_from_bbox(
                bbox,
                network_type="walk",
            )
        return self._cached_graphs[cache_key]

    def _compute_bbox(
        self,
        orig_point: tuple[float, float],
        dest_point: tuple[float, float],
    ) -> tuple[float, float, float, float]:
        orig_lat, orig_lon = orig_point
        dest_lat, dest_lon = dest_point

        center_lat = (orig_lat + dest_lat) / 2.0
        lat_margin = self._SUBGRAPH_MARGIN_METERS / 111_320.0
        lon_denominator = max(111_320.0 * abs(math.cos(math.radians(center_lat))), 1.0)
        lon_margin = self._SUBGRAPH_MARGIN_METERS / lon_denominator

        min_lat = min(orig_lat, dest_lat) - lat_margin
        max_lat = max(orig_lat, dest_lat) + lat_margin
        min_lon = min(orig_lon, dest_lon) - lon_margin
        max_lon = max(orig_lon, dest_lon) + lon_margin
        return min_lat, min_lon, max_lat, max_lon

    def nearest_node(self, graph, lat: float, lon: float) -> Node:
        node_id = ox.nearest_nodes(graph, lon, lat)
        node_data = graph.nodes[node_id]
        return Node(id=str(node_id), lat=node_data["y"], lon=node_data["x"])

    def find_shortest_route(self, graph, orig: Node, dest: Node) -> Route:
        orig_id, dest_id = int(orig.id), int(dest.id)
        path = nx.shortest_path(graph, orig_id, dest_id, weight="length")
        length = nx.shortest_path_length(graph, orig_id, dest_id, weight="length")
        return Route(node_ids=tuple(str(n) for n in path), length=length)

    def find_scenic_route(self, graph, orig: Node, dest: Node, scenic_index) -> Route:
        orig_id, dest_id = int(orig.id), int(dest.id)
        weight_fn = make_edge_weight_fn(graph, scenic_index)
        heuristic_fn = make_heuristic_fn(graph)
        path = nx.astar_path(graph, orig_id, dest_id, heuristic=heuristic_fn, weight=weight_fn)
        length = sum(
            min(
                (
                    edge_data.get("length", 0)
                    for edge_data in graph.get_edge_data(path[i], path[i + 1], default={}).values()
                    if isinstance(edge_data, dict)
                ),
                default=0,
            )
            for i in range(len(path) - 1)
        )
        return Route(node_ids=tuple(str(n) for n in path), length=length)