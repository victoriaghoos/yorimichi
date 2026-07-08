"""
Infrastructure adapter: FastAPI entrypoint. Exposes the existing
PlanScenicRouteUseCase over HTTP.
"""

from fastapi import FastAPI

from yorimichi.application.plan_route_use_case import PlanScenicRouteUseCase
from yorimichi.infrastructure.osmnx_graph_repository import OSMnxGraphRepository
from yorimichi.infrastructure.osmnx_scenic_data_provider import OSMnxScenicDataProvider

app = FastAPI(title="Yorimichi API", description="Scenic route planning for Higashiyama, Kyoto")

graph_repo = OSMnxGraphRepository()
scenic_provider = OSMnxScenicDataProvider()
use_case = PlanScenicRouteUseCase(graph_repo, scenic_provider)


@app.get("/route")
def get_route(
    place: str,
    orig_lat: float,
    orig_lon: float,
    dest_lat: float,
    dest_lon: float,
):
    result = use_case.execute(place, (orig_lat, orig_lon), (dest_lat, dest_lon))
    return {
        "baseline": {
            "node_ids": result.baseline_route.node_ids,
            "length_meters": result.baseline_route.length,
        },
        "scenic": {
            "node_ids": result.scenic_route.node_ids,
            "length_meters": result.scenic_route.length,
        },
    }