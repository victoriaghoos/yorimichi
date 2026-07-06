import osmnx as ox
import networkx as nx
import numpy as np
from scipy.spatial import cKDTree

PLACE = "Higashiyama Ward, Kyoto, Japan"

# The scenic penalty ranges from 1.0 (no discount, far from anything scenic)
# down to (1.0 - MAX_SCENIC_DISCOUNT) at the closest possible proximity.
# Kept as a single named constant so the "best case" value used by the
# heuristic can never silently drift out of sync with the actual penalty logic.
MAX_SCENIC_DISCOUNT = 0.4
BEST_CASE_SCENIC_PENALTY = 1.0 - MAX_SCENIC_DISCOUNT


def get_scenic_points(place):
    """Fetch temples, shrines, parks, and attractions from OSM as scenic reference points."""
    tags = {
        "amenity": ["place_of_worship"],
        "historic": ["temple", "shrine", "monument"],
        "leisure": ["park", "garden"],
        "tourism": ["attraction", "viewpoint"],
    }
    scenic_gdf = ox.features_from_place(place, tags)
    print(f"Found {len(scenic_gdf)} scenic points")
    return scenic_gdf


def build_scenic_lookup(scenic_gdf):
    """Build a fast nearest-neighbor lookup (KD-tree) for scenic points.

    Coordinates are stored and queried in degrees (lat/lon), not meters:
    see compute_scenic_penalty's max_influence_dist_degrees parameter.
    """
    projected = ox.projection.project_gdf(scenic_gdf)
    centroids_projected = projected.geometry.centroid
    centroids = centroids_projected.to_crs(scenic_gdf.crs)
    coords = np.array([[pt.y, pt.x] for pt in centroids])
    tree = cKDTree(coords)
    return tree


def compute_scenic_penalty(edge_midpoint_lat, edge_midpoint_lon, tree, max_influence_dist_degrees=0.003):
    """
    Calculate a penalty factor for an edge based on distance to the nearest scenic point.

    max_influence_dist_degrees is in DEGREES (~0.003 degrees ≈ 300m at this latitude),
    matching the units stored in the KD-tree built by build_scenic_lookup. This is a
    different unit than the METERS used elsewhere (e.g. edge "length" attributes and
    the great_circle heuristic distance).
    """
    dist, _ = tree.query([edge_midpoint_lat, edge_midpoint_lon])
    proximity = max(0, 1 - (dist / max_influence_dist_degrees))  # 1 = close, 0 = far
    return 1.0 - (proximity * MAX_SCENIC_DISCOUNT)


def make_edge_weight_fn(graph, tree):
    """Returns a function networkx can use as an edge-weight during A*."""
    def weight_fn(u, v, data):
        length = data.get("length", 1.0)
        u_lat, u_lon = graph.nodes[u]["y"], graph.nodes[u]["x"]
        v_lat, v_lon = graph.nodes[v]["y"], graph.nodes[v]["x"]
        mid_lat, mid_lon = (u_lat + v_lat) / 2, (u_lon + v_lon) / 2
        penalty = compute_scenic_penalty(mid_lat, mid_lon, tree)
        return length * penalty
    return weight_fn


def make_heuristic_fn(graph, best_case_penalty=BEST_CASE_SCENIC_PENALTY):
    """
    Heuristic for A*: straight-line distance (in meters, via great_circle) scaled by
    the best possible penalty, so the heuristic never overestimates the actual
    scenic-weighted cost (remains admissible).
    """
    def heuristic_fn(u, v):
        u_lat, u_lon = graph.nodes[u]["y"], graph.nodes[u]["x"]
        v_lat, v_lon = graph.nodes[v]["y"], graph.nodes[v]["x"]
        straight_line_dist = ox.distance.great_circle(u_lat, u_lon, v_lat, v_lon)
        return straight_line_dist * best_case_penalty
    return heuristic_fn


def main():
    print(f"Fetching graph for: {PLACE}")
    graph = ox.graph_from_place(PLACE, network_type="walk")
    print(f"Nodes: {len(graph.nodes)}, Edges: {len(graph.edges)}")

    scenic_points = get_scenic_points(PLACE)
    tree = build_scenic_lookup(scenic_points)

    orig_point = (34.9949, 135.7850)  # Kiyomizu-dera
    dest_point = (35.0038, 135.7788)  # Yasaka Shrine

    orig_node = ox.nearest_nodes(graph, orig_point[1], orig_point[0])
    dest_node = ox.nearest_nodes(graph, dest_point[1], dest_point[0])

    # Baseline: regular shortest distance
    baseline_route = nx.shortest_path(graph, orig_node, dest_node, weight="length")
    baseline_length = nx.shortest_path_length(graph, orig_node, dest_node, weight="length")
    print(f"\nBaseline route: {len(baseline_route)} nodes, {baseline_length:.1f}m")

    # S-A*: scenic-weighted route
    weight_fn = make_edge_weight_fn(graph, tree)
    heuristic_fn = make_heuristic_fn(graph)

    scenic_route = nx.astar_path(graph, orig_node, dest_node, heuristic=heuristic_fn, weight=weight_fn)
    print(f"Scenic route: {len(scenic_route)} nodes")

    # how long is the scenic route in actual meters (not scenic-weighted)?
    scenic_actual_length = sum(
        graph.edges[scenic_route[i], scenic_route[i + 1], 0].get("length", 0)
        for i in range(len(scenic_route) - 1)
    )
    print(f"Scenic route actual length: {scenic_actual_length:.1f}m")
    print(f"Difference vs baseline: {scenic_actual_length - baseline_length:+.1f}m")

    ox.plot_graph_routes(
        graph,
        [baseline_route, scenic_route],
        route_colors=["red", "gold"],
        route_linewidths=3,
        node_size=0,
    )


if __name__ == "__main__":
    main()