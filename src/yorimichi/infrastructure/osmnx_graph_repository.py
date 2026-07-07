"""
Infrastructure adapter: concrete IGraphRepository implementation.
Wraps OSMnx graph-fetching and nearest-node lookup, exposing only the
Domain-facing get_graph()/nearest_node() contract.
"""

import osmnx as ox

from yorimichi.domain.entities import Node
from yorimichi.domain.repositories import IGraphRepository


class OSMnxGraphRepository(IGraphRepository):
    def get_graph(self, place: str):
        return ox.graph_from_place(place, network_type="walk")

    def nearest_node(self, graph, lat: float, lon: float) -> Node:
        node_id = ox.nearest_nodes(graph, lon, lat)
        node_data = graph.nodes[node_id]
        return Node(id=str(node_id), lat=node_data["y"], lon=node_data["x"])