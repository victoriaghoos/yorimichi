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
DEFAULT_BOOST_MULTIPLIER = 1.5


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
    boost_categories: str | None = None,
    category_boosts: str | None = None,
    use_case: PlanScenicRouteUseCase = Depends(get_use_case),
) -> RouteResponse:
    """
    boost_categories: optional comma-separated list of categories to boost
    using DEFAULT_BOOST_MULTIPLIER (e.g. "nature,parks").

    category_boosts: optional explicit comma-separated mapping in the form
    "category:multiplier" (e.g. "nature:1.5,shrines_temples:0.7").

    categories is kept as a backwards-compatible alias for boost_categories.
    """
    category_boost_map = _parse_category_boosts(categories, boost_categories, category_boosts)
    result = use_case.execute(place, (orig_lat, orig_lon), (dest_lat, dest_lon), category_boost_map)

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


def _parse_category_boosts(
    categories: str | None,
    boost_categories: str | None,
    category_boosts: str | None,
) -> dict[str, float] | None:
    boost_map: dict[str, float] = {}

    for raw in (categories, boost_categories):
        if not raw:
            continue
        for category in raw.split(","):
            cleaned = category.strip()
            if cleaned:
                boost_map[cleaned] = DEFAULT_BOOST_MULTIPLIER

    if category_boosts:
        for item in category_boosts.split(","):
            entry = item.strip()
            if not entry:
                continue

            if ":" not in entry:
                raise DomainException(
                    f"Invalid category_boosts entry '{entry}'. Use 'category:multiplier'."
                )

            category, raw_multiplier = entry.split(":", maxsplit=1)
            category_name = category.strip()
            if not category_name:
                raise DomainException(
                    f"Invalid category_boosts entry '{entry}'. Category name is empty."
                )

            try:
                multiplier = float(raw_multiplier)
            except ValueError as exc:
                raise DomainException(
                    f"Invalid multiplier '{raw_multiplier}' for category '{category_name}'."
                ) from exc

            if multiplier <= 0:
                raise DomainException(
                    f"Invalid multiplier '{multiplier}' for category '{category_name}'. Must be > 0."
                )

            boost_map[category_name] = multiplier

    return boost_map or None