import osmnx as ox
import networkx as nx
import numpy as np
from scipy.spatial import cKDTree

PLACE = "Higashiyama Ward, Kyoto, Japan"

TEST_PAIRS = [
    ("Kiyomizu-dera to Yasaka Shrine", (34.9949, 135.7850), (35.0038, 135.7788)),
    ("Kiyomizu-dera to Kodai-ji", (34.9949, 135.7850), (35.0028, 135.7795)),
    ("Yasaka Shrine to Chion-in", (35.0038, 135.7788), (35.0053, 135.7830)),
    ("Kiyomizu-dera to Nanzen-ji", (34.9949, 135.7850), (35.0114, 135.7935)),
]

# The scenic penalty ranges from 1.0 (no discount, far from anything scenic)
# down to (1.0 - MAX_SCENIC_DISCOUNT) at the closest possible proximity.
# Kept as a single named constant so the "best case" value used by the
# heuristic can never silently drift out of sync with the actual penalty logic.
MAX_SCENIC_DISCOUNT = 0.4
BEST_CASE_SCENIC_PENALTY = 1.0 - MAX_SCENIC_DISCOUNT

# Weight per scenic category: a temple/shrine matters more than a generic "attraction" tag.
# Higher weight = stronger scenic pull (bigger discount when nearby).
POI_TYPE_WEIGHTS = {
    "temple": 1.0,
    "shrine": 1.0,
    "wayside_shrine": 1.0,
    "monument": 0.8,
    "place_of_worship": 0.9,
    "park": 0.6,
    "garden": 0.7,
    "attraction": 0.5,
    "viewpoint": 0.6,
}
DEFAULT_POI_WEIGHT = 0.5

# Penalty multiplier for busy/unattractive road types, based on OSM's `highway` tag.
# Factor > 1.0 makes these edges more "expensive" in the scenic-weighted cost,
# discouraging routes that pass through car-heavy arterial roads.
BUSY_ROAD_PENALTIES = {
    "trunk": 1.6,
    "trunk_link": 1.5,
    "primary": 1.5,
    "primary_link": 1.4,
    "secondary": 1.3,
    "secondary_link": 1.25,
}
DEFAULT_ROAD_PENALTY = 1.0  # neutral: no penalty, no discount


def get_scenic_points(place):
    """Fetch temples, shrines, parks, and attractions from OSM as scenic reference points."""
    tags = {
        "amenity": ["place_of_worship"],
        "historic": ["temple", "shrine", "monument"],
        "building": ["temple"],
        "leisure": ["park", "garden"],
        "tourism": ["attraction", "viewpoint"],
    }
    scenic_gdf = ox.features_from_place(place, tags)
    print(f"Found {len(scenic_gdf)} scenic points")
    return scenic_gdf


def get_poi_weight(row):
    """Look up the scenic weight for a POI row based on whichever tag matched."""
    for tag_col in ("historic", "amenity", "leisure", "tourism", "building"):
        value = row.get(tag_col)
        if value in POI_TYPE_WEIGHTS:
            return POI_TYPE_WEIGHTS[value]

    # Fallback: Japanese temples/shrines are commonly tagged by religion even when
    # the primary category tags vary between data contributors.
    if row.get("religion") in ("buddhist", "shinto"):
        return 1.0

    return DEFAULT_POI_WEIGHT


def build_scenic_lookup(scenic_gdf):
    """
    Build a fast nearest-neighbor lookup (KD-tree) for scenic points, along with
    a parallel array of per-point weights (indexed the same as the tree's points).

    Coordinates are stored and queried in degrees (lat/lon), not meters:
    see compute_scenic_penalty's max_influence_dist_degrees parameter.
    """
    projected = ox.projection.project_gdf(scenic_gdf)
    centroids_projected = projected.geometry.centroid
    centroids = centroids_projected.to_crs(scenic_gdf.crs)
    coords = np.array([[pt.y, pt.x] for pt in centroids])

    weights = np.array([get_poi_weight(row) for _, row in scenic_gdf.iterrows()])

    tree = cKDTree(coords)
    return tree, weights


def compute_scenic_penalty(edge_midpoint_lat, edge_midpoint_lon, tree, weights, max_influence_dist_degrees=0.003):
    """
    Calculate a penalty factor for an edge based on distance to the nearest scenic point,
    scaled by that point's category weight (e.g. a temple pulls harder than a generic attraction).

    max_influence_dist_degrees is in DEGREES (~0.003 degrees ≈ 300m at this latitude),
    matching the units stored in the KD-tree built by build_scenic_lookup. This is a
    different unit than the METERS used elsewhere (e.g. edge "length" attributes and
    the great_circle heuristic distance).
    """
    dist, idx = tree.query([edge_midpoint_lat, edge_midpoint_lon])
    poi_weight = weights[idx]
    proximity = max(0, 1 - (dist / max_influence_dist_degrees)) * poi_weight
    return 1.0 - (proximity * MAX_SCENIC_DISCOUNT)


def get_road_penalty(edge_data):
    """
    Look up the busy-road penalty for an edge based on its OSM `highway` tag.
    OSMnx sometimes stores `highway` as a list (when an edge has multiple tags);
    in that case, use the most severe (highest) penalty among them.
    """
    highway = edge_data.get("highway")
    if highway is None:
        return DEFAULT_ROAD_PENALTY

    if isinstance(highway, list):
        penalties = [BUSY_ROAD_PENALTIES.get(h, DEFAULT_ROAD_PENALTY) for h in highway]
        return max(penalties)

    return BUSY_ROAD_PENALTIES.get(highway, DEFAULT_ROAD_PENALTY)


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


def compute_route(graph, tree, weights, orig_point, dest_point):
    """Compute both the baseline (shortest) and scenic (S-A*) routes for a coordinate pair."""
    orig_node = ox.nearest_nodes(graph, orig_point[1], orig_point[0])
    dest_node = ox.nearest_nodes(graph, dest_point[1], dest_point[0])

    baseline_route = nx.shortest_path(graph, orig_node, dest_node, weight="length")
    baseline_length = nx.shortest_path_length(graph, orig_node, dest_node, weight="length")

    weight_fn = make_edge_weight_fn(graph, tree, weights)
    heuristic_fn = make_heuristic_fn(graph)
    scenic_route = nx.astar_path(graph, orig_node, dest_node, heuristic=heuristic_fn, weight=weight_fn)
    scenic_length = sum(
        graph.edges[scenic_route[i], scenic_route[i + 1], 0].get("length", 0)
        for i in range(len(scenic_route) - 1)
    )

    return {
        "baseline_route": baseline_route,
        "baseline_length": baseline_length,
        "scenic_route": scenic_route,
        "scenic_length": scenic_length,
    }


def print_route_comparison(label, result):
    diff = result["scenic_length"] - result["baseline_length"]
    print(
        f"{label}: baseline={result['baseline_length']:.1f}m, "
        f"scenic={result['scenic_length']:.1f}m, diff={diff:+.1f}m"
    )


def main():
    print(f"Fetching graph for: {PLACE}")
    graph = ox.graph_from_place(PLACE, network_type="walk")
    print(f"Nodes: {len(graph.nodes)}, Edges: {len(graph.edges)}")

    scenic_points = get_scenic_points(PLACE)
    tree, weights = build_scenic_lookup(scenic_points)

    print("\nComparing baseline vs scenic routes across multiple point pairs:")
    results = {}
    for label, orig_point, dest_point in TEST_PAIRS:
        result = compute_route(graph, tree, weights, orig_point, dest_point)
        print_route_comparison(label, result)
        results[label] = result

    # Visualize the first pair as a representative example
    first_label = TEST_PAIRS[0][0]
    first_result = results[first_label]
    ox.plot_graph_routes(
        graph,
        [first_result["baseline_route"], first_result["scenic_route"]],
        route_colors=["red", "gold"],
        route_linewidths=3,
        node_size=0,
    )


if __name__ == "__main__":
    main()