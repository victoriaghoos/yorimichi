import pytest

from yorimichi.domain.category_boosts import parse_category_boosts
from yorimichi.domain.exceptions import InvalidCategoryBoostException


def test_parse_category_boosts_returns_none_for_empty_inputs():
    assert parse_category_boosts(None, None, None, default_boost_multiplier=1.5) is None


def test_parse_category_boosts_applies_default_boost_to_selected_categories():
    result = parse_category_boosts("nature", "parks,waterside", None, default_boost_multiplier=1.5)

    assert result == {"nature": 1.5, "parks": 1.5, "waterside": 1.5}


def test_parse_category_boosts_explicit_values_override_default_boosts():
    result = parse_category_boosts(
        "nature,parks",
        None,
        "nature:2.0,shrines_temples:0.7",
        default_boost_multiplier=1.5,
    )

    assert result == {"nature": 2.0, "parks": 1.5, "shrines_temples": 0.7}


@pytest.mark.parametrize(
    "raw_value",
    [
        "nature",
        ":1.2",
        "nature:not_a_number",
        "nature:0",
        "nature:-0.1",
    ],
)
def test_parse_category_boosts_raises_for_invalid_entries(raw_value):
    with pytest.raises(InvalidCategoryBoostException):
        parse_category_boosts(None, None, raw_value, default_boost_multiplier=1.5)
