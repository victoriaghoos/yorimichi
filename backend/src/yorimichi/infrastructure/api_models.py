"""
Infrastructure: Pydantic models for the FastAPI layer. These are DTOs
that translate between Domain entities (Route) and the JSON shape exposed over HTTP.
"""

from pydantic import BaseModel, Field


class RouteDTO(BaseModel):
    node_ids: list[str] = Field(..., description="Ordered list of graph node IDs forming the route")
    length_meters: float = Field(..., description="Total real-world length of the route, in meters")


class RouteResponse(BaseModel):
    baseline: RouteDTO = Field(..., description="Shortest-path route (no scenic weighting)")
    scenic: RouteDTO = Field(..., description="Scenic-weighted route (S-A*)")