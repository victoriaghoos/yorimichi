"""
Domain logic for category boost parsing/validation.

This module defines the canonical rules for translating optional category
boost inputs into a normalized mapping consumed by route planning.
"""

from yorimichi.domain.exceptions import InvalidCategoryBoostException


def parse_category_boosts(
    categories: str | None,
    boost_categories: str | None,
    category_boosts: str | None,
    default_boost_multiplier: float,
) -> dict[str, float] | None:
    """
    Build a normalized category->multiplier map.

    - categories and boost_categories are comma-separated category names
      that receive default_boost_multiplier.
    - category_boosts is a comma-separated mapping: "name:multiplier".
    - Explicit entries in category_boosts override default boosts.
    """
    boost_map: dict[str, float] = {}

    for raw in (categories, boost_categories):
        if not raw:
            continue
        for category in raw.split(","):
            cleaned = category.strip()
            if cleaned:
                boost_map[cleaned] = default_boost_multiplier

    if category_boosts:
        for item in category_boosts.split(","):
            entry = item.strip()
            if not entry:
                continue

            if ":" not in entry:
                raise InvalidCategoryBoostException(
                    f"Invalid category_boosts entry '{entry}'. Use 'category:multiplier'."
                )

            category, raw_multiplier = entry.split(":", maxsplit=1)
            category_name = category.strip()
            if not category_name:
                raise InvalidCategoryBoostException(
                    f"Invalid category_boosts entry '{entry}'. Category name is empty."
                )

            try:
                multiplier = float(raw_multiplier)
            except ValueError as exc:
                raise InvalidCategoryBoostException(
                    f"Invalid multiplier '{raw_multiplier}' for category '{category_name}'."
                ) from exc

            if multiplier <= 0:
                raise InvalidCategoryBoostException(
                    f"Invalid multiplier '{multiplier}' for category '{category_name}'. Must be > 0."
                )

            boost_map[category_name] = multiplier

    return boost_map or None
