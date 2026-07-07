import osmnx as ox
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial import cKDTree

PLACE = "Higashiyama Ward, Kyoto, Japan"

TEST_PAIRS = [
    ("Kiyomizu-dera to Yasaka Shrine", (34.9949, 135.7850), (35.0038, 135.7788)),
    ("Kiyomizu-dera to Kodai-ji", (34.9949, 135.7850), (35.0028, 135.7795)),
    ("Yasaka Shrine to Chion-in", (35.0038, 135.7788), (35.0053, 135.7830)),
    ("Kiyomizu-dera to Nanzen-ji", (34.9949, 135.7850), (35.0114, 135.7935)),
]

# The scenic penalty ranges from 1.0 (no discount, far from anything scenic)
# down to (1.0 - MAX_SCENIC_DISCOUNT) at the closest proximity.
# Kept as a single named constant so the "best case" value used by the
# heuristic can never silently drift out of sync with the actual penalty logic.
MAX_SCENIC_DISCOUNT = 0.4
BEST_CASE_SCENIC_PENALTY = 1.0 - MAX_SCENIC_DISCOUNT

# High-confidence weights for specific, known-good OSM tag values.
# Higher weight = stronger scenic pull (bigger discount when nearby).
POI_TYPE_WEIGHTS = {
    # Religious / sacred sites
    "temple": 1.0,
    "shrine": 1.0,
    "wayside_shrine": 1.0,
    "place_of_worship": 0.9,
    "monastery": 0.9,
    "church": 0.85,
    "wayside_chapel": 0.7,
    "wayside_cross": 0.7,

    # Historic structures / landmarks
    "castle": 0.9,
    "heritage": 0.85,
    "manor": 0.8,
    "monument": 0.8,
    "city_gate": 0.75,
    "citywalls": 0.7,
    "tower": 0.75,
    "archaeological_site": 0.7,
    "ruins": 0.7,
    "fort": 0.7,
    "bridge": 0.65,

    # Nature / leisure
    "park": 0.6,
    "garden": 0.7,
    "attraction": 0.5,
    "viewpoint": 0.6,

    # Lower-confidence / generic
    "memorial": 0.65,
    "house": 0.4,
}

# OSM keys where an unlisted value is still plausibly scenic (e.g. an
# unfamiliar historic=* value we haven't explicitly weighted yet). Values
# under these keys that AREN'T in POI_TYPE_WEIGHTS still get a moderate
# "probably somewhat scenic" weight rather than falling all the way to the
# generic default: this is what protects against silently underweighting
# real scenic points we simply haven't encountered/named yet.
LIKELY_SCENIC_KEYS = {"historic", "tourism", "leisure"}
LIKELY_SCENIC_FALLBACK_WEIGHT = 0.55

# Values that are technically under a "likely scenic" key but are clearly
# NOT scenic in practice: an exclusion list, so these don't accidentally
# get the moderate fallback weight above.
EXCLUDED_VALUES = {
    "boundary_stone", "charcoal_pile", "shieling", "bomb_crater", "railway",
    "mine", "mine_shaft", "milestone", "aircraft", "cannon", "wreck", "stone",
    "hollow_way", "roman_road", "bunker", "maritime", "farm", "locomotive",
    "grave", "naval", "military", "battlefield", "tank", "railway_car",
    "aqueduct", "tunnel", "substation", "yes", "no",
}

DEFAULT_POI_WEIGHT = 0.4  # generic fallback for anything not covered above

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
    """
    Fetch a broad set of OSM features that could plausibly be scenic. `historic`
    is queried broadly (all values) since scenic-relevant historic tags vary too
    much across regions/contributors to enumerate exhaustively upfront: see
    POI_TYPE_WEIGHTS and get_poi_weight for how the resulting noise is filtered
    and weighted afterward.
    """
    tags = {
        "historic": True,
        "amenity": ["place_of_worship"],
        "leisure": ["park", "garden"],
        "tourism": ["attraction", "viewpoint"],
        "building": ["temple"],
    }
    scenic_gdf = ox.features_from_place(place, tags)
    print(f"Found {len(scenic_gdf)} scenic points")
    return scenic_gdf


def get_poi_weight(row):
    """
    Look up the scenic weight for a POI row. Prefers a small, curated set of
    high-confidence weights for known categories; falls back to a moderate
    "probably somewhat scenic" weight for unlisted-but-plausible values under
    likely-scenic keys, rather than immediately dropping to the generic default.
    """
    for tag_col in ("historic", "amenity", "leisure", "tourism", "building"):
        value = row.get(tag_col)
        if value is None:
            continue

        if value in POI_TYPE_WEIGHTS:
            return POI_TYPE_WEIGHTS[value]

        if value not in EXCLUDED_VALUES and tag_col in LIKELY_SCENIC_KEYS:
            return LIKELY_SCENIC_FALLBACK_WEIGHT

    if row.get("religion") in ("buddhist", "shinto"):
        return 1.0

    # General notability signal: a Wikipedia/Wikidata link
    if row.get("wikipedia") is not None or row.get("wikidata") is not None:
        return 0.9

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


def plot_route_comparison(graph, result, label):
    """
    Plot baseline vs scenic route for a single pair, zoomed to the relevant area
    with a legend, so the divergence is clearly visible without extra context.
    """
    fig, ax = ox.plot_graph_routes(
        graph,
        [result["baseline_route"], result["scenic_route"]],
        route_colors=["red", "gold"],
        route_linewidths=3,
        node_size=0,
        show=False,
        close=False,
    )

    all_route_nodes = set(result["baseline_route"]) | set(result["scenic_route"])
    lats = [graph.nodes[n]["y"] for n in all_route_nodes]
    lons = [graph.nodes[n]["x"] for n in all_route_nodes]
    margin = 0.002  # circa 200m padding
    ax.set_xlim(min(lons) - margin, max(lons) + margin)
    ax.set_ylim(min(lats) - margin, max(lats) + margin)

    ax.plot([], [], color="red", linewidth=3, label="Shortest route")
    ax.plot([], [], color="gold", linewidth=3, label="Scenic route (S-A*)")
    ax.legend(loc="lower right", facecolor="black", labelcolor="white", framealpha=0.8)

    ax.set_title(label, color="white", fontsize=12)
    return fig, ax


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

    for label, result in results.items():
        plot_route_comparison(graph, result, label)

    plt.show()


if __name__ == "__main__":
    main()