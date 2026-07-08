"""
Infrastructure: SQLAlchemy ORM models for PostGIS-backed graph storage.
These are database-mapping concerns only.

Tables are prefixed with "yorimichi_" to avoid naming collisions with
PostGIS' own built-in extension tables — specifically, postgis_tiger_geocoder
ships with a table literally named "edges", which silently caused
SQLAlchemy's create_all() to skip creating our own edges table entirely
(it believed the table already existed).
"""

from sqlalchemy import Column, String, Float, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from geoalchemy2 import Geometry

Base = declarative_base()


class NodeModel(Base):
    __tablename__ = "yorimichi_nodes"

    id = Column(String, primary_key=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    geom = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)


class EdgeModel(Base):
    __tablename__ = "yorimichi_edges"

    id = Column(String, primary_key=True)
    from_node_id = Column(String, ForeignKey("yorimichi_nodes.id"), nullable=False)
    to_node_id = Column(String, ForeignKey("yorimichi_nodes.id"), nullable=False)
    length = Column(Float, nullable=False)
    highway_tag = Column(String, nullable=True)

    from_node = relationship("NodeModel", foreign_keys=[from_node_id])
    to_node = relationship("NodeModel", foreign_keys=[to_node_id])