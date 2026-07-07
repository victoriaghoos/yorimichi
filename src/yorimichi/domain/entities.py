"""
Domain entities: pure data structures with no external dependencies.
These are the only objects the Domain layer understands: networkx graphs,
OSMnx data, etc. never appear here or anywhere downstream in Domain code.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Node:
    id: str
    lat: float
    lon: float

@dataclass(frozen=True)
class Edge:
    from_node: Node
    to_node: Node
    length: float
    highway_tag: str | list[str] | None = None
    
@dataclass(frozen=True)
class Route:
    node_ids: tuple[str, ...]
    length: float