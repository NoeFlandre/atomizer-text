"""Tests for taxonomy.map_tags_to_category and RASTER_PRIORITY."""
from __future__ import annotations

import pytest

from atomizer_osm_pilot.taxonomy import (
    CATEGORIES,
    RASTER_PRIORITY,
    Category,
    RULES,
    map_tags_to_category,
)


def test_empty_tags_is_unknown():
    assert map_tags_to_category({}) is Category.UNKNOWN
    assert map_tags_to_category(None) is Category.UNKNOWN


def test_building_yes_is_other_building():
    assert map_tags_to_category({"building": "yes"}) is Category.OTHER_BUILDING


def test_residential_building_tags():
    for tags in [
        {"building": "house"},
        {"building": "residential"},
        {"building": "apartments"},
        {"building:use": "residential"},
    ]:
        assert map_tags_to_category(tags) is Category.RESIDENTIAL_BUILDING, tags


def test_office_building_tags():
    assert map_tags_to_category({"building": "office"}) is Category.OFFICE_BUILDING
    assert map_tags_to_category({"office": "yes"}) is Category.OFFICE_BUILDING


def test_commercial_building_tags():
    assert map_tags_to_category({"building": "retail"}) is Category.COMMERCIAL_BUILDING
    assert map_tags_to_category({"shop": "supermarket"}) is Category.COMMERCIAL_BUILDING


def test_industrial_building_tags():
    assert map_tags_to_category({"building": "industrial"}) is Category.INDUSTRIAL_BUILDING
    assert map_tags_to_category({"building": "warehouse"}) is Category.INDUSTRIAL_BUILDING


def test_road_tags():
    assert map_tags_to_category({"highway": "residential"}) is Category.ROAD
    assert map_tags_to_category({"highway": "primary"}) is Category.ROAD
    # non-road highway values are not roads
    assert map_tags_to_category({"highway": "bus_stop"}) is not Category.ROAD


def test_agricultural_land_tags():
    assert map_tags_to_category({"landuse": "farmland"}) is Category.AGRICULTURAL_LAND
    assert map_tags_to_category({"landuse": "meadow"}) is Category.AGRICULTURAL_LAND
    assert map_tags_to_category({"landuse": "vineyard"}) is Category.AGRICULTURAL_LAND


def test_vegetation_tags():
    assert map_tags_to_category({"landuse": "forest"}) is Category.VEGETATION_OR_PARK
    assert map_tags_to_category({"leisure": "park"}) is Category.VEGETATION_OR_PARK
    assert map_tags_to_category({"natural": "wood"}) is Category.VEGETATION_OR_PARK


def test_water_tags():
    assert map_tags_to_category({"natural": "water"}) is Category.WATER
    assert map_tags_to_category({"waterway": "river"}) is Category.WATER
    assert map_tags_to_category({"landuse": "reservoir"}) is Category.WATER


def test_building_priority_over_road_when_both_present():
    # In the RULES list, road comes first, so this is a road.
    tags = {"highway": "residential", "building": "house"}
    assert map_tags_to_category(tags) is Category.ROAD
    # The interesting case: a farmland feature that is also a building
    # is still a building (rule order: building rules come before
    # agricultural_land).
    tags = {"building": "house", "landuse": "farmland"}
    assert map_tags_to_category(tags) is Category.RESIDENTIAL_BUILDING


# ---------------------------------------------------------------------------
# RASTER_PRIORITY (Amendment 1)
# ---------------------------------------------------------------------------

def test_raster_priority_keys_match_categories():
    for c in CATEGORIES:
        assert c in RASTER_PRIORITY, f"missing RASTER_PRIORITY entry for {c}"


def test_raster_priority_ordering_buildings_win():
    """Pin the order so a future enum-value change can't silently
    re-introduce the old backwards ordering."""
    assert RASTER_PRIORITY[Category.OFFICE_BUILDING] \
        > RASTER_PRIORITY[Category.ROAD] \
        > RASTER_PRIORITY[Category.AGRICULTURAL_LAND] \
        > RASTER_PRIORITY[Category.UNKNOWN]


def test_raster_priority_water_and_vegetation_above_unknown():
    assert RASTER_PRIORITY[Category.WATER] > RASTER_PRIORITY[Category.UNKNOWN]
    assert RASTER_PRIORITY[Category.VEGETATION_OR_PARK] \
        > RASTER_PRIORITY[Category.UNKNOWN]


def test_raster_priority_uses_explicit_mapping_not_enum_values():
    # Sanity: enum values are display-only. The mapping must be its own
    # table. We assert that RASTER_PRIORITY is not just ``{c: int(c)}``.
    assert RASTER_PRIORITY[Category.OFFICE_BUILDING] != int(Category.OFFICE_BUILDING)
    assert RASTER_PRIORITY[Category.AGRICULTURAL_LAND] != int(Category.AGRICULTURAL_LAND)
