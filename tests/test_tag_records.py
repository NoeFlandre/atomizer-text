"""Tests for tag_records.build_tag_records."""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import box

from atomizer_osm_pilot.raster_io import RasterInfo
from atomizer_osm_pilot.tag_records import build_tag_records
from rasterio.transform import Affine


def _trivial_raster_info() -> RasterInfo:
    transform = Affine(0.5, 0, 0, 0, -0.5, 50)
    data = np.zeros((3, 100, 100), dtype=np.uint8)
    return RasterInfo(data=data, transform=transform, crs="EPSG:32631",
                      width=100, height=100, count=3)


def test_build_records_empty(synthetic_raster):
    gdf = gpd.GeoDataFrame({"tags": [], "geometry": []}, crs="EPSG:32631")
    assert build_tag_records(gdf, np.zeros((10, 10), dtype=np.int32),
                             synthetic_raster.transform) == []


def test_build_records_two_features(synthetic_raster):
    cat_map = np.zeros((synthetic_raster.height, synthetic_raster.width),
                       dtype=np.int32)
    # Use the synthetic_gdf via the rasterize pipeline so the GDF is in the
    # same CRS and the tag categories are populated. For this test we just
    # pass a small hand-built GDF.
    t = synthetic_raster.transform
    px = t.a
    origin_x, origin_y = t.c, t.f
    a = box(origin_x + 2 * px, origin_y - 10 * px,
            origin_x + 8 * px, origin_y - 5 * px)
    b = box(origin_x + 12 * px, origin_y - 10 * px,
            origin_x + 18 * px, origin_y - 5 * px)
    gdf = gpd.GeoDataFrame(
        {
            "osmid": ["a", "b"],
            "tags": [{"building": "house"}, {"highway": "residential"}],
            "geometry": [a, b],
        },
        crs="EPSG:32631",
    )
    records = build_tag_records(gdf, cat_map, synthetic_raster.transform)
    assert len(records) == 2
    cats = {r["category"] for r in records}
    assert cats == {"RESIDENTIAL_BUILDING", "ROAD"}
    for r in records:
        assert r["pixel_count"] > 0
        assert isinstance(r["raw_tags"], dict)
        assert r["centroid_xy"] is not None
        assert r["raw_tags"] is not gdf.iloc[0]["tags"]  # copy, not same ref


def test_raw_tags_are_copied_not_mutated(synthetic_raster):
    t = synthetic_raster.transform
    px = t.a
    origin_x, origin_y = t.c, t.f
    a = box(origin_x + 1 * px, origin_y - 5 * px,
            origin_x + 5 * px, origin_y - 2 * px)
    tags = {"building": "house"}
    gdf = gpd.GeoDataFrame(
        {"osmid": ["a"], "tags": [tags], "geometry": [a]},
        crs="EPSG:32631",
    )
    records = build_tag_records(gdf, np.zeros((synthetic_raster.height,
                                               synthetic_raster.width),
                                              dtype=np.int32),
                                synthetic_raster.transform)
    assert records[0]["raw_tags"] == tags
    records[0]["raw_tags"]["injected"] = True
    assert "injected" not in gdf.iloc[0]["tags"]
