from fastapi.testclient import TestClient

from yorimichi.infrastructure import fastapi_app
from yorimichi.application.plan_route_use_case import PlanRouteResult
from yorimichi.domain.entities import Route
from yorimichi.domain.exceptions import CoordinatesOutOfRangeException


class FakeUseCase:
    """Fake PlanScenicRouteUseCase for isolated endpoint testing, no real OSM calls."""
    def __init__(self, should_raise=False):
        self.should_raise = should_raise
        self.last_category_boosts = None

    def execute(self, place, orig_point, dest_point, category_boosts=None):
        self.last_category_boosts = category_boosts
        if self.should_raise:
            raise CoordinatesOutOfRangeException("Origin", orig_point[0], orig_point[1], 14_000_000, place)
        return PlanRouteResult(
            baseline_route=Route(node_ids=("1", "2", "3"), length=150.0),
            scenic_route=Route(node_ids=("1", "4", "3"), length=180.0),
            baseline_coordinates=((35.0, 135.0), (35.0005, 135.0005), (35.001, 135.001)),
            scenic_coordinates=((35.0, 135.0), (35.0007, 135.0003), (35.001, 135.001)),
        )


def test_get_route_returns_200_with_valid_data():
    use_case = FakeUseCase(should_raise=False)
    fastapi_app.configure(use_case)
    client = TestClient(fastapi_app.app)

    response = client.get("/route", params={
        "place": "Fake Place", "orig_lat": 35.0, "orig_lon": 135.0,
        "dest_lat": 35.001, "dest_lon": 135.001,
    })

    assert response.status_code == 200
    data = response.json()
    assert data["baseline"]["length_meters"] == 150.0
    assert data["scenic"]["length_meters"] == 180.0
    assert len(data["baseline"]["coordinates"]) == 3
    assert len(data["scenic"]["coordinates"]) == 3
    assert use_case.last_category_boosts is None


def test_get_route_supports_boost_categories_param():
    use_case = FakeUseCase(should_raise=False)
    fastapi_app.configure(use_case)
    client = TestClient(fastapi_app.app)

    response = client.get("/route", params={
        "place": "Fake Place", "orig_lat": 35.0, "orig_lon": 135.0,
        "dest_lat": 35.001, "dest_lon": 135.001,
        "boost_categories": "nature,parks",
    })

    assert response.status_code == 200
    assert use_case.last_category_boosts == {"nature": fastapi_app.DEFAULT_BOOST_MULTIPLIER, "parks": fastapi_app.DEFAULT_BOOST_MULTIPLIER}


def test_get_route_supports_explicit_category_boosts_param():
    use_case = FakeUseCase(should_raise=False)
    fastapi_app.configure(use_case)
    client = TestClient(fastapi_app.app)

    response = client.get("/route", params={
        "place": "Fake Place", "orig_lat": 35.0, "orig_lon": 135.0,
        "dest_lat": 35.001, "dest_lon": 135.001,
        "category_boosts": "nature:1.5,shrines_temples:0.7",
    })

    assert response.status_code == 200
    assert use_case.last_category_boosts == {"nature": 1.5, "shrines_temples": 0.7}


def test_get_route_returns_400_for_invalid_category_boosts():
    use_case = FakeUseCase(should_raise=False)
    fastapi_app.configure(use_case)
    client = TestClient(fastapi_app.app)

    response = client.get("/route", params={
        "place": "Fake Place", "orig_lat": 35.0, "orig_lon": 135.0,
        "dest_lat": 35.001, "dest_lon": 135.001,
        "category_boosts": "nature:not_a_number",
    })

    assert response.status_code == 400
    assert "Invalid multiplier" in response.json()["detail"]


def test_get_route_returns_400_for_out_of_range_coordinates():
    fastapi_app.configure(FakeUseCase(should_raise=True))
    client = TestClient(fastapi_app.app)

    response = client.get("/route", params={
        "place": "Fake Place", "orig_lat": 0.0, "orig_lon": 0.0,
        "dest_lat": 35.001, "dest_lon": 135.001,
    })

    assert response.status_code == 400
    assert "coordinates may be outside this area" in response.json()["detail"]