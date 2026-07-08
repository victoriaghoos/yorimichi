import pytest

from yorimichi.domain.exceptions import DomainException, CoordinatesOutOfRangeException


def test_coordinates_out_of_range_exception_inherits_from_domain_exception():
    """
    Confirms the inheritance hierarchy: this is what allows FastAPI's single
    exception_handler(DomainException) to catch every domain-rule violation,
    not just this specific one.
    """
    exc = CoordinatesOutOfRangeException("Origin", 0.0, 0.0, 14000000.0, "Higashiyama Ward, Kyoto, Japan")
    assert isinstance(exc, DomainException)


def test_coordinates_out_of_range_exception_stores_context():
    """Confirms the rich context (lat/lon/distance/place) is accessible on the exception object."""
    exc = CoordinatesOutOfRangeException("Destination", 35.001, 135.001, 2500.0, "Higashiyama Ward, Kyoto, Japan")

    assert exc.label == "Destination"
    assert exc.lat == 35.001
    assert exc.lon == 135.001
    assert exc.distance_meters == 2500.0
    assert exc.place == "Higashiyama Ward, Kyoto, Japan"


def test_coordinates_out_of_range_exception_message_is_readable():
    """Confirms the generated message includes the key details a caller needs to debug the issue."""
    exc = CoordinatesOutOfRangeException("Origin", 0.0, 0.0, 14000000, "Higashiyama Ward, Kyoto, Japan")

    message = str(exc)
    assert "Origin" in message
    assert "14000000" in message or "14,000,000" in message
    assert "Higashiyama Ward, Kyoto, Japan" in message