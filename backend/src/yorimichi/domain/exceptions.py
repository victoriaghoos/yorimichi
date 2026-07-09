"""
Domain-level exceptions: represent business-rule violations, not
infrastructure failures. All Domain exceptions inherit from DomainException,
so Infrastructure layers (e.g. FastAPI) can catch this one base class and
translate any domain-rule violation into an appropriate response (e.g. a
400 Bad Request), while genuinely unexpected exceptions still surface as
500 errors rather than being silently caught here.
"""


class DomainException(Exception):
    """Base class for all Domain-layer business rule violations."""
    pass


class CoordinatesOutOfRangeException(DomainException):
    """Raised when a given coordinate is unreasonably far from the nearest known road."""

    def __init__(self, label: str, lat: float, lon: float, distance_meters: float, place: str):
        self.label = label
        self.lat = lat
        self.lon = lon
        self.distance_meters = distance_meters
        self.place = place
        super().__init__(
            f"{label} coordinates ({lat}, {lon}) are {distance_meters:.0f}m from the "
            f"nearest known road in '{place}': coordinates may be outside this area."
        )


class InvalidCategoryBoostException(DomainException):
    """Raised when the category_boosts query parameter is malformed."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)