"""
Infrastructure adapter: PostGIS-backed IGraphRepository implementation.
"""

import networkx as nx
from shapely.geometry import Point
from geoalchemy2.shape import from_shape
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from yorimichi.domain.entities import Node, Route
from yorimichi.domain.repositories import IGraphRepository
from yorimichi.infrastructure.osmnx_routing_adapter import make_edge_weight_fn, make_heuristic_fn
from yorimichi.infrastructure.postgis_models import NodeModel, EdgeModel


class PostGISGraphRepository(IGraphRepository):
    def __init__(self, database_url: str):
        self._engine = create_engine(database_url)
        self._Session = sessionmaker(bind=self._engine)
        self._cached_graphs = {}

    def get_graph(self, place: str):
        if place in self._cached_graphs:
            return self._cached_graphs[place]

        session = self._Session()
        try:
            graph = nx.MultiDiGraph(crs="EPSG:4326")

            nodes = session.query(NodeModel).all()
            for node in nodes:
                graph.add_node(node.id, y=node.lat, x=node.lon)

            edges = session.query(EdgeModel).all()
            for edge in edges:
                graph.add_edge(
                    edge.from_node_id,
                    edge.to_node_id,
                    length=edge.length,
                    highway=edge.highway_tag,
                )

            self._cached_graphs[place] = graph
            return graph
        finally:
            session.close()

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


    def find_scenic_route(self, graph, orig: Node, dest: Node, scenic_provider) -> Route:
        orig_id, dest_id = orig.id, dest.id
        weight_fn = make_edge_weight_fn(graph, scenic_provider)
        heuristic_fn = make_heuristic_fn(graph)
        path = nx.astar_path(graph, orig_id, dest_id, heuristic=heuristic_fn, weight=weight_fn)
        length = sum(
            graph.edges[path[i], path[i + 1], 0].get("length", 0)
            for i in range(len(path) - 1)
        )
        return Route(node_ids=tuple(str(n) for n in path), length=length)