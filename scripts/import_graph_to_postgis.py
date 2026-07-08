"""
One-off script: imports the Higashiyama walking-network graph from OSMnx
into the yorimichi_nodes/yorimichi_edges PostGIS tables. Run once (or
whenever you want to refresh the data): PostGISGraphRepository queries
against this pre-loaded data rather than calling OSMnx live.
"""

import osmnx as ox
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from yorimichi.infrastructure.postgis_models import Base, NodeModel, EdgeModel

DATABASE_URL = "postgresql://postgres:yourpassword@localhost:5432/yorimichi"
PLACE = "Higashiyama Ward, Kyoto, Japan"


def main():
    print(f"Fetching graph for: {PLACE}")
    graph = ox.graph_from_place(PLACE, network_type="walk")
    print(f"Nodes: {len(graph.nodes)}, Edges: {len(graph.edges)}")

    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)  # ensures tables exist, idempotent
    Session = sessionmaker(bind=engine)
    session = Session()

    print("Clearing existing data...")
    session.query(EdgeModel).delete()
    session.query(NodeModel).delete()
    session.commit()

    print("Importing nodes...")
    node_count = 0
    for node_id, data in graph.nodes(data=True):
        point = Point(data["x"], data["y"])  # Point(lon, lat) 
        node = NodeModel(
            id=str(node_id),
            lat=float(data["y"]),
            lon=float(data["x"]),
            geom=from_shape(point, srid=4326),
        )
        session.add(node)
        node_count += 1
    session.commit()
    print(f"Imported {node_count} nodes.")

    print("Importing edges...")
    edge_count = 0
    for u, v, key, data in graph.edges(keys=True, data=True):
        highway = data.get("highway")
        if isinstance(highway, list):
            highway = highway[0]  # simplify: store the first tag if multiple

        edge = EdgeModel(
            id=f"{u}_{v}_{key}",
            from_node_id=str(u),
            to_node_id=str(v),
            length=float(data.get("length", 0.0)),  # force plain Python float, not numpy.float64
            highway_tag=highway,
        )
        session.add(edge)
        edge_count += 1
    session.commit()
    print(f"Imported {edge_count} edges.")

    session.close()
    print("Import complete.")


if __name__ == "__main__":
    main()