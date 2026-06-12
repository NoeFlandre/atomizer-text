"""OSM tag -> semantic category taxonomy.

Two things live here:

1. ``RULES``: a small, editable, prioritized list of predicates that map a
   raw OSM tag dict to a single ``Category``. Edit this list to iterate on
   the taxonomy after seeing real data.

2. ``RASTER_PRIORITY``: an explicit, separate mapping from ``Category`` to
   a burn priority used when features overlap on the raster grid
   (see :mod:`atomizer_osm_pilot.rasterize`).

   This is **deliberately not derived from the ``Category`` enum value**.
   Enum values are for display / serialization only; rasterization priority
   is a separate concept (Amendment 1 of the v1 plan).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Callable, Dict, List


class Category(IntEnum):
    """Fixed set of semantic categories the raster can take per pixel.

    Enum values are display-only and have no relation to rasterization
    priority (see ``RASTER_PRIORITY``).
    """

    UNKNOWN = 0
    RESIDENTIAL_BUILDING = 1
    OFFICE_BUILDING = 2
    COMMERCIAL_BUILDING = 3
    INDUSTRIAL_BUILDING = 4
    OTHER_BUILDING = 5
    ROAD = 6
    AGRICULTURAL_LAND = 7
    VEGETATION_OR_PARK = 8
    WATER = 9


# Convenience tuple of all categories in enum order, for stats / visualization.
CATEGORIES: tuple[Category, ...] = tuple(Category)


# ---------------------------------------------------------------------------
# Rule list
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Rule:
    """A single taxonomy rule: when ``matches(tags)`` is true, assign
    ``category`` to the feature.
    """

    name: str
    matches: Callable[[dict], bool]
    category: Category


def _has(tags: dict, key: str) -> bool:
    return key in tags and tags[key] not in (None, "", "no")


def _is_building(tags: dict) -> bool:
    if not _has(tags, "building"):
        return False
    val = str(tags["building"]).lower()
    return val not in {"no"}


def _building_value_in(tags: dict, allowed: set[str]) -> bool:
    return _is_building(tags) and str(tags["building"]).lower() in allowed


def _matches_residential_building(tags: dict) -> bool:
    if _building_value_in(tags, {"house", "residential", "apartments",
                                 "detached", "semidetached", "terrace",
                                 "bungalow", "dormitory"}):
        return True
    if str(tags.get("building:use", "")).lower() == "residential":
        return True
    return False


def _matches_office(tags: dict) -> bool:
    if _building_value_in(tags, {"office"}):
        return True
    if _has(tags, "office"):
        return True
    return False


def _matches_commercial(tags: dict) -> bool:
    if _building_value_in(tags, {"retail", "commercial", "supermarket",
                                 "kiosk"}):
        return True
    if _has(tags, "shop"):
        return True
    return False


def _matches_industrial(tags: dict) -> bool:
    if _building_value_in(tags, {"industrial", "warehouse", "factory",
                                 "manufacture"}):
        return True
    if str(tags.get("landuse", "")).lower() == "industrial" and _is_building(tags):
        return True
    return False


def _matches_other_building(tags: dict) -> bool:
    return _is_building(tags)


def _matches_road(tags: dict) -> bool:
    if not _has(tags, "highway"):
        return False
    val = str(tags["highway"]).lower()
    # Exclude non-road highway values.
    return val not in {"bus_stop", "stop", "platform", "traffic_signals",
                       "turning_circle", "construction", "proposed",
                       "no", "elevator", "rest_area"}


def _matches_agricultural(tags: dict) -> bool:
    val = str(tags.get("landuse", "")).lower()
    if val in {"farmland", "farmyard", "meadow", "orchard", "vineyard",
               "plant_nursery", "greenhouse_horticulture"}:
        return True
    return False


def _matches_vegetation(tags: dict) -> bool:
    val = str(tags.get("landuse", "")).lower()
    if val in {"forest", "grass", "recreation_ground", "village_green",
               "cemetery"}:
        return True
    if str(tags.get("leisure", "")).lower() in {"park", "garden", "nature_reserve"}:
        return True
    if str(tags.get("natural", "")).lower() in {"wood", "grassland", "heath",
                                                 "scrub", "tree_row"}:
        return True
    return False


def _matches_water(tags: dict) -> bool:
    if str(tags.get("natural", "")).lower() == "water":
        return True
    if _has(tags, "waterway"):
        return True
    val = str(tags.get("landuse", "")).lower()
    if val in {"reservoir", "basin"}:
        return True
    return False


# RULES: tried in order; first match wins. Order is the rule priority for
# *taxonomy* (which category to assign). Burn priority for overlapping
# features is separate; see RASTER_PRIORITY below.
RULES: List[Rule] = [
    Rule("road", _matches_road, Category.ROAD),
    Rule("residential_building", _matches_residential_building,
         Category.RESIDENTIAL_BUILDING),
    Rule("office_building", _matches_office, Category.OFFICE_BUILDING),
    Rule("industrial_building", _matches_industrial, Category.INDUSTRIAL_BUILDING),
    Rule("commercial_building", _matches_commercial, Category.COMMERCIAL_BUILDING),
    Rule("agricultural_land", _matches_agricultural, Category.AGRICULTURAL_LAND),
    Rule("vegetation_or_park", _matches_vegetation, Category.VEGETATION_OR_PARK),
    Rule("water", _matches_water, Category.WATER),
    Rule("other_building", _matches_other_building, Category.OTHER_BUILDING),
]


def map_tags_to_category(tags: dict | None) -> Category:
    """Map a raw OSM tag dict to a single :class:`Category`.

    Returns :attr:`Category.UNKNOWN` for empty or ``None`` input, or when
    no rule matches.
    """
    if not tags:
        return Category.UNKNOWN
    for rule in RULES:
        try:
            if rule.matches(tags):
                return rule.category
        except Exception:
            # A malformed tag dict should not blow up the pipeline; skip.
            continue
    return Category.UNKNOWN


# ---------------------------------------------------------------------------
# Rasterization priority (Amendment 1)
# ---------------------------------------------------------------------------
#
# Lower number = drawn first = lower priority (gets overwritten).
# Higher number = drawn last = higher priority (wins on overlap).
#
# Buildings should win over roads, which should win over landuse / vegetation
# / water, which should win over unspecified (UNKNOWN) pixels.
#
# This mapping is intentionally separate from the ``Category`` enum values.
# The enum values are display/serialization only; do not use them for burn
# order.
RASTER_PRIORITY: Dict[Category, int] = {
    Category.UNKNOWN: 0,
    Category.AGRICULTURAL_LAND: 1,
    Category.VEGETATION_OR_PARK: 1,
    Category.WATER: 1,
    Category.ROAD: 2,
    Category.RESIDENTIAL_BUILDING: 3,
    Category.OFFICE_BUILDING: 3,
    Category.COMMERCIAL_BUILDING: 3,
    Category.INDUSTRIAL_BUILDING: 3,
    Category.OTHER_BUILDING: 3,
}
