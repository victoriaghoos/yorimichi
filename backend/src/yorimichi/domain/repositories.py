"""
Domain-owned repository ports (abstract interfaces). contract: only values it needs (a scenic
penalty for a coordinate, a road penalty for an edge), never for the underlying
data structures (KD-trees, GeoDataFrames, etc.) used to compute them.
"""

from abc import ABC, abstractmethod

from yorimichi.domain.entities import Node, Route


class IGraphRepository(ABC):
    """Provides access to the street network for a route corridor."""

    @abstractmethod
    def get_graph(
        self,
        orig_point: tuple[float, float],
        dest_point: tuple[float, float],
    ):
        """
        Returns an opaque graph handle for the route corridor implied by origin
        and destination coordinates. The Domain never inspects this object
        directly — it's passed back into this same repository's other methods
        (e.g. nearest_node) to resolve real data.
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
    def find_scenic_route(self, graph, orig: Node, dest: Node, scenic_index) -> Route:
        """Returns the scenic (S-A*) route between two nodes."""
        raise NotImplementedError


class IScenicIndex(ABC):
    @abstractmethod
    def get_scenic_penalty(self, lat: float, lon: float) -> float:
        raise NotImplementedError


class IScenicDataProvider(ABC):
    @abstractmethod
    def load(
        self,
        orig_point: tuple[float, float],
        dest_point: tuple[float, float],
        category_boosts: dict[str, float] | None = None,
    ) -> IScenicIndex:
        """
        Loads/prepares scenic data for the route corridor implied by origin and
        destination coordinates and returns an immutable scenic index object.

        category_boosts applies a multiplier per category (e.g. {"nature": 1.5}),
        where 1.0 keeps the normal strength, >1.0 boosts and <1.0 weakens.
        Categories not listed are treated as 1.0 (neutral, still counted).
        """
        raise NotImplementedError