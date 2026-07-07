"""
Infrastructure adapter: concrete IGraphRepository implementation.
Owns all networkx-specific routing execution (shortest_path, astar_path)
"""

import osmnx as ox
import networkx as nx

from yorimichi.domain.entities import Node, Route
from yorimichi.domain.repositories import IGraphRepository
from yorimichi.infrastructure.osmnx_routing_adapter import make_edge_weight_fn, make_heuristic_fn


class OSMnxGraphRepository(IGraphRepository):
    def get_graph(self, place: str):
        return ox.graph_from_place(place, network_type="walk")

    def nearest_node(self, graph, lat: float, lon: float) -> Node:
        node_id = ox.nearest_nodes(graph, lon, lat)
        node_data = graph.nodes[node_id]
        return Node(id=str(node_id), lat=node_data["y"], lon=node_data["x"])

    def find_shortest_route(self, graph, orig: Node, dest: Node) -> Route:
        orig_id, dest_id = int(orig.id), int(dest.id)
        path = nx.shortest_path(graph, orig_id, dest_id, weight="length")
        length = nx.shortest_path_length(graph, orig_id, dest_id, weight="length")
        return Route(node_ids=tuple(str(n) for n in path), length=length)

    def find_scenic_route(self, graph, orig: Node, dest: Node, scenic_provider) -> Route:
        orig_id, dest_id = int(orig.id), int(dest.id)
        weight_fn = make_edge_weight_fn(graph, scenic_provider)
        heuristic_fn = make_heuristic_fn(graph)
        path = nx.astar_path(graph, orig_id, dest_id, heuristic=heuristic_fn, weight=weight_fn)
        length = sum(
            graph.edges[path[i], path[i + 1], 0].get("length", 0)
            for i in range(len(path) - 1)
        )
        return Route(node_ids=tuple(str(n) for n in path), length=length)