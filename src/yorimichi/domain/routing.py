"""
Domain-layer S-A* routing logic. Builds the edge-weight and heuristic
functions used by networkx's astar_path: these encode the core scenic
routing algorithm and its admissibility guarantee.
"""

import osmnx as ox

from yorimichi.domain.scoring import (
    compute_scenic_penalty,
    get_road_penalty,
    BEST_CASE_SCENIC_PENALTY,
)


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
    Heuristic for A*: straight-line distance (in meters, via great_circle) scaled by
    the best-case scenic multiplier (BEST_CASE_SCENIC_PENALTY) and the best-case
    road multiplier (1.0, i.e. a neutral road with no busy-road penalty), so the
    heuristic never overestimates the actual scenic- and road-weighted cost.
    """
    def heuristic_fn(u, v):
        u_lat, u_lon = graph.nodes[u]["y"], graph.nodes[u]["x"]
        v_lat, v_lon = graph.nodes[v]["y"], graph.nodes[v]["x"]
        straight_line_dist = ox.distance.great_circle(u_lat, u_lon, v_lat, v_lon)
        return straight_line_dist * best_case_penalty
    return heuristic_fn