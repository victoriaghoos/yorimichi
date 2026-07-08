"""
Infrastructure adapter: FastAPI entrypoint. Exposes PlanScenicRouteUseCase
over HTTP via dependency injection: this file does NOT instantiate any
concrete Infrastructure implementations itself. That wiring belongs
exclusively to the composition root (main.py).
"""

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from yorimichi.application.plan_route_use_case import PlanScenicRouteUseCase
from yorimichi.domain.exceptions import DomainException
from yorimichi.infrastructure.api_models import RouteDTO, RouteResponse

app = FastAPI(title="Yorimichi API", description="Scenic route planning for Higashiyama, Kyoto")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    categories: str | None = None,
    use_case: PlanScenicRouteUseCase = Depends(get_use_case),
) -> RouteResponse:
    """
    categories: optional comma-separated list of active scenic categories
    (e.g. "shrines_temples,parks"). If omitted, all categories are active
    (default, unfiltered behavior).
    """
    category_list = categories.split(",") if categories else None
    result = use_case.execute(place, (orig_lat, orig_lon), (dest_lat, dest_lon), category_list)

    return RouteResponse(
        baseline=RouteDTO(
            node_ids=list(result.baseline_route.node_ids),
            length_meters=result.baseline_route.length,
            coordinates=list(result.baseline_coordinates),
        ),
        scenic=RouteDTO(
            node_ids=list(result.scenic_route.node_ids),
            length_meters=result.scenic_route.length,
            coordinates=list(result.scenic_coordinates),
        ),
    )