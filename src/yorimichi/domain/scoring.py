"""
Domain-layer scenic and road scoring logic. Pure Python, no external
infrastructure dependencies (no direct osmnx/networkx calls): this module
only computes numeric weights/penalties from the data it's given.
"""

# The scenic penalty ranges from 1.0 (no discount, far from anything scenic)
# down to (1.0 - MAX_SCENIC_DISCOUNT) at the closest possible proximity.
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

    if row.get("wikipedia") is not None or row.get("wikidata") is not None:
        return 0.9

    return DEFAULT_POI_WEIGHT


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