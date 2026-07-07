"""
Domain-layer S-A* routing logic. Pure business logic operating exclusively
on Node/Edge entities: zero knowledge of networkx, osmnx, or any external
graph library.
"""

import math

from yorimichi.domain.entities import Node, Edge
from yorimichi.domain.scoring import (
    compute_scenic_penalty,
    get_road_penalty,
    BEST_CASE_SCENIC_PENALTY,
)

EARTH_RADIUS_METERS = 6_371_000


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in meters."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_METERS * c


def calculate_edge_cost(edge: Edge, tree, weights) -> float:
    """
    Pure domain calculation of an edge's scenic- and road-weighted cost.
    Takes only a domain Edge (which itself holds Node references): no
    networkx (u, v, data) in here.
    """
    mid_lat = (edge.from_node.lat + edge.to_node.lat) / 2
    mid_lon = (edge.from_node.lon + edge.to_node.lon) / 2

    scenic_penalty = compute_scenic_penalty(mid_lat, mid_lon, tree, weights)
    road_penalty = get_road_penalty({"highway": edge.highway_tag})

    return edge.length * scenic_penalty * road_penalty


def calculate_heuristic(from_node: Node, to_node: Node, best_case_penalty: float = BEST_CASE_SCENIC_PENALTY) -> float:
    """
    Admissible heuristic: straight-line distance scaled by the best-case
    scenic multiplier, so it never overestimates the true remaining cost.
    """
    straight_line_dist = haversine_distance(from_node.lat, from_node.lon, to_node.lat, to_node.lon)
    return straight_line_dist * best_case_penalty