"""
Infrastructure: SQLAlchemy ORM models for PostGIS-backed graph storage.
These are database-mapping concerns only.

Tables are prefixed with "yorimichi_" to avoid naming collisions with
PostGIS' own built-in extension tables — specifically, postgis_tiger_geocoder
ships with a table literally named "edges", which silently caused
SQLAlchemy's create_all() to skip creating our own edges table entirely
(it believed the table already existed).
"""

from geoalchemy2 import Geometry
from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class NodeModel(Base):
    __tablename__ = "yorimichi_nodes"

    id: Mapped[str] = mapped_column(primary_key=True)
    lat: Mapped[float]
    lon: Mapped[float]
    geom = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)


class EdgeModel(Base):
    __tablename__ = "yorimichi_edges"

    id: Mapped[str] = mapped_column(primary_key=True)
    from_node_id: Mapped[str] = mapped_column(ForeignKey("yorimichi_nodes.id"))
    to_node_id: Mapped[str] = mapped_column(ForeignKey("yorimichi_nodes.id"))
    length: Mapped[float]
    highway_tag: Mapped[str | None]

    from_node = relationship("NodeModel", foreign_keys=[from_node_id])
    to_node = relationship("NodeModel", foreign_keys=[to_node_id])