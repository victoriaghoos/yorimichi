"""
Scalable OSM PBF -> PostGIS importer for yorimichi_nodes/yorimichi_edges.

Key differences vs the old prototype:
1. Ingests from .osm.pbf via CLI args (no hardcoded place).
2. Supports partitioned loading by --region-id or --tile-id.
3. Uses append-by-default with UPSERTs (optional --truncate).
4. Writes in batches via execute_values for performance.
"""

import argparse
import math
import os
from dataclasses import dataclass
from pathlib import Path

import osmium
from dotenv import load_dotenv
from psycopg2.extras import execute_values
from sqlalchemy import create_engine

from yorimichi.infrastructure.postgis_models import Base

load_dotenv()

DATABASE_URL = os.environ.get("POSTGIS_DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "POSTGIS_DATABASE_URL is not set. Set it in your .env file or environment."
    )

EARTH_RADIUS_METERS = 6_371_000

# Region presets are intentionally coarse: they are ingestion windows,
# not final route bounds.
REGION_BBOXES = {
    "kansai": (33.00, 134.10, 35.90, 136.95),
    "kanto": (34.80, 138.60, 37.10, 141.20),
}

# OSM highway values we generally want for walking-oriented routing.
NON_WALKABLE_HIGHWAY_TAGS = {
    "motorway",
    "motorway_link",
}


@dataclass(frozen=True)
class Bounds:
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    def contains(self, lat: float, lon: float) -> bool:
        return self.min_lat <= lat <= self.max_lat and self.min_lon <= lon <= self.max_lon


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import OSM PBF graph data into PostGIS.")
    parser.add_argument(
        "--pbf-path",
        required=True,
        help="Path to an .osm.pbf file (e.g. scripts/kansai-latest.osm.pbf).",
    )

    scope_group = parser.add_mutually_exclusive_group(required=True)
    scope_group.add_argument(
        "--region-id",
        help="Region key (kansai|kanto) or explicit bbox 'min_lat,min_lon,max_lat,max_lon'.",
    )
    scope_group.add_argument(
        "--tile-id",
        help="Slippy tile id as z/x/y, used as ingestion window.",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="Batch size for upsert writes (default: 5000).",
    )
    parser.add_argument(
        "--commit-every-flushes",
        type=int,
        default=30,
        help="Commit after this many batch flushes (default: 30).",
    )
    parser.add_argument(
        "--progress-every-ways",
        type=int,
        default=200000,
        help="Print ingest progress every N parsed ways (default: 200000).",
    )

    parser.add_argument(
        "--append",
        dest="append",
        action="store_true",
        default=True,
        help="Append/upsert data (default).",
    )
    parser.add_argument(
        "--truncate",
        dest="append",
        action="store_false",
        help="Truncate nodes/edges before import.",
    )
    return parser.parse_args()


def tile_to_bounds(tile_id: str) -> Bounds:
    try:
        z_str, x_str, y_str = tile_id.split("/")
        z, x, y = int(z_str), int(x_str), int(y_str)
    except ValueError as exc:
        raise ValueError("tile-id must be in z/x/y format.") from exc

    n = 2 ** z
    lon_min = x / n * 360.0 - 180.0
    lon_max = (x + 1) / n * 360.0 - 180.0

    lat_max_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat_min_rad = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))
    lat_max = math.degrees(lat_max_rad)
    lat_min = math.degrees(lat_min_rad)

    return Bounds(min_lat=lat_min, min_lon=lon_min, max_lat=lat_max, max_lon=lon_max)


def region_to_bounds(region_id: str) -> Bounds:
    key = region_id.strip().lower()
    if key in REGION_BBOXES:
        return Bounds(*REGION_BBOXES[key])

    # Also allow explicit bbox input for ad-hoc chunking.
    parts = [p.strip() for p in region_id.split(",")]
    if len(parts) == 4:
        try:
            return Bounds(*(float(v) for v in parts))
        except ValueError as exc:
            raise ValueError("Invalid bbox values in --region-id.") from exc

    raise ValueError(
        f"Unknown region-id '{region_id}'. Use one of {sorted(REGION_BBOXES.keys())} "
        "or explicit 'min_lat,min_lon,max_lat,max_lon'."
    )


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_METERS * c


def is_walkable_way(way) -> bool:
    highway = way.tags.get("highway")
    if not highway:
        return False
    if highway in NON_WALKABLE_HIGHWAY_TAGS:
        return False
    if way.tags.get("foot") == "no":
        return False
    return True


def is_oneway_for_pedestrians(way) -> bool:
    if way.tags.get("oneway:foot") in {"yes", "1", "true"}:
        return True
    return way.tags.get("oneway") in {"yes", "1", "true"}


class PostGISBatchUpserter:
    def __init__(self, raw_connection, batch_size: int, commit_every_flushes: int):
        self._conn = raw_connection
        self._batch_size = batch_size
        self._commit_every_flushes = max(1, commit_every_flushes)
        self._node_batch: dict[str, tuple[str, float, float]] = {}
        self._edge_batch: list[tuple[str, str, str, float, str | None]] = []
        self._flushes_since_commit = 0

        self.nodes_upserted = 0
        self.edges_upserted = 0
        self.total_flushes = 0
        self.total_commits = 0

    def add_node(self, node_id: str, lat: float, lon: float):
        self._node_batch[node_id] = (node_id, lat, lon)
        if len(self._node_batch) >= self._batch_size:
            self.flush_nodes()

    def add_edge(self, edge_id: str, from_node_id: str, to_node_id: str, length: float, highway_tag: str | None):
        self._edge_batch.append((edge_id, from_node_id, to_node_id, length, highway_tag))
        if len(self._edge_batch) >= self._batch_size:
            # Ensure FK dependencies are persisted before writing edges.
            self.flush_nodes()
            self.flush_edges()

    def flush_nodes(self):
        if not self._node_batch:
            return

        rows = list(self._node_batch.values())
        sql = """
            INSERT INTO yorimichi_nodes (id, lat, lon, geom)
            SELECT v.id, v.lat, v.lon, ST_SetSRID(ST_MakePoint(v.lon, v.lat), 4326)
            FROM (VALUES %s) AS v(id, lat, lon)
            ON CONFLICT (id) DO UPDATE
            SET lat = EXCLUDED.lat,
                lon = EXCLUDED.lon,
                geom = EXCLUDED.geom
        """

        with self._conn.cursor() as cursor:
            execute_values(cursor, sql, rows, page_size=min(len(rows), 1000))

        self.nodes_upserted += len(rows)
        self._node_batch.clear()
        self._mark_flush()

    def flush_edges(self):
        if not self._edge_batch:
            return

        sql = """
            INSERT INTO yorimichi_edges (id, from_node_id, to_node_id, length, highway_tag)
            VALUES %s
            ON CONFLICT (id) DO UPDATE
            SET from_node_id = EXCLUDED.from_node_id,
                to_node_id = EXCLUDED.to_node_id,
                length = EXCLUDED.length,
                highway_tag = EXCLUDED.highway_tag
        """

        with self._conn.cursor() as cursor:
            execute_values(cursor, sql, self._edge_batch, page_size=min(len(self._edge_batch), 1000))

        self.edges_upserted += len(self._edge_batch)
        self._edge_batch.clear()
        self._mark_flush()

    def _mark_flush(self):
        self.total_flushes += 1
        self._flushes_since_commit += 1
        if self._flushes_since_commit >= self._commit_every_flushes:
            self.commit()

    def commit(self):
        self._conn.commit()
        self.total_commits += 1
        self._flushes_since_commit = 0

    def flush_all(self):
        self.flush_nodes()
        self.flush_edges()
        if self._flushes_since_commit > 0:
            self.commit()


class PBFGraphImporter(osmium.SimpleHandler):
    def __init__(self, bounds: Bounds, writer: PostGISBatchUpserter, progress_every_ways: int):
        super().__init__()
        self._bounds = bounds
        self._writer = writer
        self._progress_every_ways = max(1, progress_every_ways)

        self.ways_seen = 0
        self.ways_used = 0
        self.segments_written = 0

    def _segment_in_bounds(self, lat1: float, lon1: float, lat2: float, lon2: float) -> bool:
        return self._bounds.contains(lat1, lon1) or self._bounds.contains(lat2, lon2)

    def way(self, way):
        self.ways_seen += 1
        if self.ways_seen % self._progress_every_ways == 0:
            # Force periodic flush/commit for long-running imports.
            self._writer.flush_all()
            print(
                "Progress: "
                f"ways_seen={self.ways_seen:,}, "
                f"ways_used={self.ways_used:,}, "
                f"segments_written={self.segments_written:,}, "
                f"nodes_upserted={self._writer.nodes_upserted:,}, "
                f"edges_upserted={self._writer.edges_upserted:,}"
                ,
                flush=True,
            )

        if not is_walkable_way(way):
            return

        if len(way.nodes) < 2:
            return

        highway = way.tags.get("highway")
        if isinstance(highway, list):
            highway = highway[0]

        oneway = is_oneway_for_pedestrians(way)
        wrote_any_for_way = False

        for index in range(len(way.nodes) - 1):
            node_a = way.nodes[index]
            node_b = way.nodes[index + 1]

            if not (node_a.location.valid() and node_b.location.valid()):
                continue

            lat1, lon1 = float(node_a.location.lat), float(node_a.location.lon)
            lat2, lon2 = float(node_b.location.lat), float(node_b.location.lon)

            if not self._segment_in_bounds(lat1, lon1, lat2, lon2):
                continue

            from_id = str(node_a.ref)
            to_id = str(node_b.ref)
            length = haversine_distance(lat1, lon1, lat2, lon2)

            self._writer.add_node(from_id, lat1, lon1)
            self._writer.add_node(to_id, lat2, lon2)

            forward_edge_id = f"w{way.id}:{index}:f"
            self._writer.add_edge(forward_edge_id, from_id, to_id, length, highway)
            self.segments_written += 1
            wrote_any_for_way = True

            if not oneway:
                reverse_edge_id = f"w{way.id}:{index}:r"
                self._writer.add_edge(reverse_edge_id, to_id, from_id, length, highway)
                self.segments_written += 1

        if wrote_any_for_way:
            self.ways_used += 1


def main():
    args = parse_args()
    pbf_path = Path(args.pbf_path)
    if not pbf_path.exists():
        raise FileNotFoundError(f"PBF file not found: {pbf_path}")

    bounds = tile_to_bounds(args.tile_id) if args.tile_id else region_to_bounds(args.region_id)

    print("Starting import with settings:", flush=True)
    print(f"  pbf_path   : {pbf_path}", flush=True)
    print(f"  bounds     : {bounds}", flush=True)
    print(f"  batch_size : {args.batch_size}", flush=True)
    print(f"  commit_every_flushes : {args.commit_every_flushes}", flush=True)
    print(f"  progress_every_ways  : {args.progress_every_ways}", flush=True)
    print(f"  mode       : {'append/upsert' if args.append else 'truncate then upsert'}", flush=True)

    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)

    raw_conn = engine.raw_connection()
    try:
        if not args.append:
            print("Truncating existing graph tables...", flush=True)
            with raw_conn.cursor() as cursor:
                cursor.execute("TRUNCATE TABLE yorimichi_edges, yorimichi_nodes")
            raw_conn.commit()

        writer = PostGISBatchUpserter(
            raw_conn,
            batch_size=args.batch_size,
            commit_every_flushes=args.commit_every_flushes,
        )
        importer = PBFGraphImporter(
            bounds,
            writer,
            progress_every_ways=args.progress_every_ways,
        )

        print("Parsing PBF and ingesting in batches...", flush=True)
        importer.apply_file(str(pbf_path), locations=True)
        writer.flush_all()

        print("Import complete.", flush=True)
        print(f"  ways seen       : {importer.ways_seen:,}", flush=True)
        print(f"  ways used       : {importer.ways_used:,}", flush=True)
        print(f"  edge segments   : {importer.segments_written:,}", flush=True)
        print(f"  nodes upserted  : {writer.nodes_upserted:,}", flush=True)
        print(f"  edges upserted  : {writer.edges_upserted:,}", flush=True)
        print(f"  batch flushes   : {writer.total_flushes:,}", flush=True)
        print(f"  commits         : {writer.total_commits:,}", flush=True)
    except Exception:
        raw_conn.rollback()
        raise
    finally:
        raw_conn.close()


if __name__ == "__main__":
    main()