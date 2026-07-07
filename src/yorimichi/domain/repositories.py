"""
Domain-owned repository ports (abstract interfaces). contract: only values it needs (a scenic penalty for a coordinate, a road penalty for an edge), never for the underlying
data structures (KD-trees, GeoDataFrames, etc.) used to compute them.
"""

from abc import ABC, abstractmethod

from yorimichi.domain.entities import Node, Route


class IGraphRepository(ABC):
    """Provides access to the street network for a given place."""

    @abstractmethod
    def get_graph(self, place: str):
        """
        Returns an opaque graph handle for the given place. The Domain never
        inspects this object directly — it's passed back into this same
        repository's other methods (e.g. nearest_node) to resolve real data.
        """
        raise NotImplementedError

    @abstractmethod
    def nearest_node(self, graph, lat: float, lon: float) -> Node:
        """Returns the graph node nearest to the given coordinates, as a Domain Node."""
        raise NotImplementedError
    
    @abstractmethod
    def find_shortest_route(self, graph, orig: Node, dest: Node) -> Route:
        """Returns the shortest route (by raw distance) between two nodes."""
        raise NotImplementedError

    @abstractmethod
    def find_scenic_route(self, graph, orig: Node, dest: Node, scenic_provider) -> Route:
        """Returns the scenic (S-A*) route between two nodes."""
        raise NotImplementedError


class IScenicDataProvider(ABC):
    """
    Provides scenic scoring for coordinates, without exposing HOW that
    scoring is computed (KD-tree lookups, weight arrays, etc. stay entirely
    inside the concrete Infrastructure implementation).
    """

    @abstractmethod
    def load(self, place: str):
        """Loads/prepares scenic data for the given place (called once per session)."""
        raise NotImplementedError

    @abstractmethod
    def get_scenic_penalty(self, lat: float, lon: float) -> float:
        """Returns the scenic discount/penalty factor for a coordinate."""
        raise NotImplementedError