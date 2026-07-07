"""
Domain-layer S-A* routing logic. Builds the edge-weight and heuristic
functions used by networkx's astar_path: these encode the core scenic
routing algorithm and its admissibility guarantee.

Zero external infrastructure dependencies (no osmnx import): great-circle
distance is computed directly via the Haversine formula, so this module can
be unit-tested without installing the full geospatial stack.
"""

import math

from yorimichi.domain.scoring import (
    compute_scenic_penalty,
    get_road_penalty,
    BEST_CASE_SCENIC_PENALTY,
)

EARTH_RADIUS_METERS = 6_371_000


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Great-circle distance between two lat/lon points, in meters, using the
    Haversine formula. Replaces osmnx.distance.great_circle() so the Domain
    layer has zero dependency on external geospatial libraries.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_METERS * c


def make_edge_weight_fn(graph, tree, weights):
    """Returns a function networkx can use as an edge-weight during A*."""
    def weight_fn(u, v, data):
        length = data.get("length", 1.0)
        u_lat, u_lon = graph.nodes[u]["y"], graph.nodes[u]["x"]
        v_lat, v_lon = graph.nodes[v]["y"], graph.nodes[v]["x"]
        mid_lat, mid_lon = (u_lat + v_lat) / 2, (u_lon + v_lon) / 2

        scenic_penalty = compute_scenic_penalty(mid_lat, mid_lon, tree, weights)
        road_penalty = get_road_penalty(data)

        return length * scenic_penalty * road_penalty
    return weight_fn


def make_heuristic_fn(graph, best_case_penalty=BEST_CASE_SCENIC_PENALTY):
    """
    Heuristic for A*: straight-line distance (in meters, via Haversine formula)
    scaled by the best-case scenic multiplier (BEST_CASE_SCENIC_PENALTY) and the
    best-case road multiplier (1.0, i.e. a neutral road with no busy-road
    penalty), so the heuristic never overestimates the actual scenic- and
    road-weighted cost.
    """
    def heuristic_fn(u, v):
        u_lat, u_lon = graph.nodes[u]["y"], graph.nodes[u]["x"]
        v_lat, v_lon = graph.nodes[v]["y"], graph.nodes[v]["x"]
        straight_line_dist = haversine_distance(u_lat, u_lon, v_lat, v_lon)
        return straight_line_dist * best_case_penalty
    return heuristic_fn