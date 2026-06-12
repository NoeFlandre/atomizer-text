"""Shared synthetic fixtures for offline tests.

Both fixtures represent a small VHR tile of roughly the same on-the-ground
size (tens of meters) so test geometries are easy to reason about across the
two coordinate systems.
"""

from __future__ import annotations

import os
from pathlib import Path

from atomizer_osm_pilot._env import fix_proj_env
fix_proj_env()

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine

from atomizer_osm_pilot.raster_io import RasterInfo


# ---------------------------------------------------------------------------
# Synthetic rasters
# ---------------------------------------------------------------------------

# UTM 31N (EPSG:32631), covering France. ~0.5 m per pixel, 50x50 = ~25 m tile.
# Origin in projected meters (easting, northing).
_UTM_CRS = "EPSG:32631"
_UTM_PIXEL = 0.5  # meters per pixel
_UTM_ORIGIN_X = 500_000.0
_UTM_ORIGIN_Y = 4_640_000.0  # north-up: top of raster

# Montpellier center, in degrees. ~0.2 m/px at this latitude.
# 0.0000018 deg ~ 0.2 m (cos(lat) * 111_320 m/deg).
_WGS84_CRS = "EPSG:4326"
_WGS84_LON = 3.8767
_WGS84_LAT = 43.6112
_WGS84_PIXEL = 0.0000018  # degrees per pixel


def _synthetic_utm() -> RasterInfo:
    width = height = 50
    data = np.zeros((3, height, width), dtype=np.uint8)
    # Make a simple gradient so visualizers have something to show.
    for i in range(height):
        data[:, i, :] = np.linspace(0, 255, width, dtype=np.uint8)
    # affine: top-left pixel center = (origin_x, origin_y), pixel size = (+px, -px)
    transform = Affine(_UTM_PIXEL, 0.0, _UTM_ORIGIN_X,
                       0.0, -_UTM_PIXEL, _UTM_ORIGIN_Y)
    return RasterInfo(data=data, transform=transform, crs=_UTM_CRS,
                      width=width, height=height, count=3)


def _synthetic_wgs84() -> RasterInfo:
    """Independent WGS84 fixture (Amendment 2): transform in degrees, centered
    on Montpellier. Lon increases east (right), lat increases north (up)."""
    width = height = 50
    data = np.full((3, height, width), 128, dtype=np.uint8)
    # Top-left pixel center at (lon, lat); pixel size (+east, +north).
    transform = Affine(_WGS84_PIXEL, 0.0, _WGS84_LON,
                       0.0, _WGS84_PIXEL, _WGS84_LAT)
    return RasterInfo(data=data, transform=transform, crs=_WGS84_CRS,
                      width=width, height=height, count=3)


@pytest.fixture
def synthetic_raster() -> RasterInfo:
    return _synthetic_utm()


@pytest.fixture
def synthetic_raster_wgs84() -> RasterInfo:
    return _synthetic_wgs84()


# ---------------------------------------------------------------------------
# Synthetic GeoDataFrame
# ---------------------------------------------------------------------------

@pytest.fixture
def synthetic_gdf(synthetic_raster):
    """Five hand-placed features in EPSG:32631 covering known regions of the
    synthetic_raster tile. Coordinates are in projected meters.
    """
    import geopandas as gpd
    from shapely.geometry import LineString, Polygon, box

    transform = synthetic_raster.transform
    # Top-left of the raster in projected coords (Affine.c, Affine.f).
    origin_x = transform.c
    origin_y = transform.f
    px = transform.a  # pixel width (meters)

    # Helper: pixel (col, row) top-left -> projected (x, y) top-left of that
    # pixel. Row 0 is at the top (highest y).
    def pixel_xy(col: int, row: int) -> tuple[float, float]:
        x = origin_x + col * px
        y = origin_y - row * px
        return x, y

    # 1. Residential building: cols 2..9, rows 2..7 -> ~4 m x 2.5 m
    bx, by = pixel_xy(2, 2)
    res = box(bx, by - 5 * px, bx + 8 * px, by)

    # 2. Office building: cols 12..19, rows 2..7
    bx, by = pixel_xy(12, 2)
    off = box(bx, by - 5 * px, bx + 8 * px, by)

    # 3. building=yes (no further tags): cols 22..29, rows 2..7
    bx, by = pixel_xy(22, 2)
    byes = box(bx, by - 5 * px, bx + 8 * px, by)

    # 4. Highway=residential as buffered line, rows 14..16
    bx, by = pixel_xy(0, 15)
    road = LineString([(bx, by), (origin_x + 50 * px, by)]).buffer(px * 1.2)

    # 5. landuse=farmland: rows 25..44, cols 0..49
    bx, by = pixel_xy(0, 25)
    farm = box(bx, by - 20 * px, origin_x + 50 * px, by)

    gdf = gpd.GeoDataFrame(
        {
            "osmid": ["res-1", "off-1", "byes-1", "road-1", "farm-1"],
            "tags": [
                {"building": "house", "building:use": "residential"},
                {"building": "office"},
                {"building": "yes"},
                {"highway": "residential"},
                {"landuse": "farmland"},
            ],
        },
        geometry=[res, off, byes, road, farm],
        crs=_UTM_CRS,
    )
    return gdf


@pytest.fixture
def fake_fetcher(synthetic_gdf):
    """Callable that returns the synthetic_gdf (reprojected to WGS84) instead
    of hitting the Overpass network.
    """
    def _fetcher(bbox_wgs84, tag_keys):
        return synthetic_gdf.to_crs("EPSG:4326").copy()
    return _fetcher


# ---------------------------------------------------------------------------
# Tiny on-disk GeoTIFF used by the CLI smoke test
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def tiny_tif_path(tmp_path_factory) -> Path:
    """A small programmatically generated GeoTIFF the CLI smoke test runs
    against. Not depended on by unit tests.
    """
    info = _synthetic_utm()
    path = tmp_path_factory.mktemp("cli") / "tiny.tif"
    with rasterio.open(
        path, "w",
        driver="GTiff",
        height=info.height,
        width=info.width,
        count=info.count,
        dtype=info.data.dtype,
        crs=info.crs,
        transform=info.transform,
    ) as dst:
        dst.write(info.data)
    return path
