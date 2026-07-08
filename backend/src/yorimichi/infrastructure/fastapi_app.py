"""
Infrastructure adapter: FastAPI entrypoint. Exposes PlanScenicRouteUseCase
over HTTP via dependency injection.
"""

from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse

from yorimichi.application.plan_route_use_case import PlanScenicRouteUseCase
from yorimichi.domain.exceptions import DomainException
from yorimichi.infrastructure.api_models import RouteDTO, RouteResponse

app = FastAPI(title="Yorimichi API", description="Scenic route planning for Higashiyama, Kyoto")

_use_case: PlanScenicRouteUseCase | None = None


def configure(use_case: PlanScenicRouteUseCase):
    """Called once by the composition root to inject the fully-wired use case."""
    global _use_case
    _use_case = use_case


def get_use_case() -> PlanScenicRouteUseCase:
    if _use_case is None:
        raise RuntimeError("fastapi_app.configure() must be called before serving requests.")
    return _use_case


@app.exception_handler(DomainException)
def domain_exception_handler(request: Request, exc: DomainException):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/route", response_model=RouteResponse)
def get_route(
    place: str,
    orig_lat: float,
    orig_lon: float,
    dest_lat: float,
    dest_lon: float,
    use_case: PlanScenicRouteUseCase = Depends(get_use_case),
) -> RouteResponse:
    result = use_case.execute(place, (orig_lat, orig_lon), (dest_lat, dest_lon))

    return RouteResponse(
        baseline=RouteDTO(node_ids=list(result.baseline_route.node_ids), length_meters=result.baseline_route.length),
        scenic=RouteDTO(node_ids=list(result.scenic_route.node_ids), length_meters=result.scenic_route.length),
    )