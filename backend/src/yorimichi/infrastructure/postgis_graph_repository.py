"""
Infrastructure adapter: PostGIS-backed IGraphRepository implementation.
"""

import math

import networkx as nx
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import and_, create_engine
from sqlalchemy.orm import aliased, sessionmaker

from yorimichi.domain.entities import Node, Route
from yorimichi.domain.repositories import IGraphRepository
from yorimichi.infrastructure.osmnx_routing_adapter import make_edge_weight_fn, make_heuristic_fn
from yorimichi.infrastructure.postgis_models import EdgeModel, NodeModel


class PostGISGraphRepository(IGraphRepository):
    _SUBGRAPH_MARGIN_METERS = 1500.0

    def __init__(self, database_url: str):
        self._engine = create_engine(database_url)
        self._Session = sessionmaker(bind=self._engine)
        self._cached_graphs: dict[str, nx.MultiDiGraph] = {}

    def get_graph(
        self,
        orig_point: tuple[float, float],
        dest_point: tuple[float, float],
    ):
        cache_key = self._make_cache_key(orig_point, dest_point)
        if cache_key in self._cached_graphs:
            return self._cached_graphs[cache_key]

        session = self._Session()
        try:
            graph = nx.MultiDiGraph(crs="EPSG:4326")

            min_lat, min_lon, max_lat, max_lon = self._compute_bbox(orig_point, dest_point)
            nodes = (
                session.query(NodeModel)
                .filter(
                    and_(
                        NodeModel.lat >= min_lat,
                        NodeModel.lat <= max_lat,
                        NodeModel.lon >= min_lon,
                        NodeModel.lon <= max_lon,
                    )
                )
                .all()
            )

            for node in nodes:
                graph.add_node(node.id, y=node.lat, x=node.lon)

            from_node = aliased(NodeModel)
            to_node = aliased(NodeModel)
            edges = (
                session.query(EdgeModel)
                .join(from_node, from_node.id == EdgeModel.from_node_id)
                .join(to_node, to_node.id == EdgeModel.to_node_id)
                .filter(
                    and_(
                        from_node.lat >= min_lat,
                        from_node.lat <= max_lat,
                        from_node.lon >= min_lon,
                        from_node.lon <= max_lon,
                        to_node.lat >= min_lat,
                        to_node.lat <= max_lat,
                        to_node.lon >= min_lon,
                        to_node.lon <= max_lon,
                    )
                )
                .all()
            )

            for edge in edges:
                graph.add_edge(
                    edge.from_node_id,
                    edge.to_node_id,
                    length=edge.length,
                    highway=edge.highway_tag,
                )

            self._cached_graphs[cache_key] = graph
            return graph
        finally:
            session.close()

    def _make_cache_key(
        self,
        orig_point: tuple[float, float],
        dest_point: tuple[float, float],
    ) -> str:
        min_lat, min_lon, max_lat, max_lon = self._compute_bbox(orig_point, dest_point)
        return f"{min_lat:.6f}|{min_lon:.6f}|{max_lat:.6f}|{max_lon:.6f}"

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
        """
        Finds the nearest node using a real PostGIS spatial query (ST_Distance
        against the geom column), rather than a Python-side search.
        """
        session = self._Session()
        try:
            query_point = from_shape(Point(lon, lat), srid=4326)
            nearest = (
                session.query(NodeModel)
                .order_by(NodeModel.geom.distance_centroid(query_point))
                .first()
            )
            if nearest is None:
                raise RuntimeError("No nodes found in the database: did you run the import script?")
            return Node(id=nearest.id, lat=nearest.lat, lon=nearest.lon)
        finally:
            session.close()

    def find_shortest_route(self, graph, orig: Node, dest: Node) -> Route:
        orig_id, dest_id = orig.id, dest.id
        path = nx.shortest_path(graph, orig_id, dest_id, weight="length")
        length = nx.shortest_path_length(graph, orig_id, dest_id, weight="length")
        return Route(node_ids=tuple(str(n) for n in path), length=length)


    def find_scenic_route(self, graph, orig: Node, dest: Node, scenic_index) -> Route:
        orig_id, dest_id = orig.id, dest.id
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