"""Tests for raster_io.RasterInfo and load_raster()."""
from __future__ import annotations

import numpy as np
import pytest
import rasterio

from atomizer_osm_pilot.raster_io import RasterInfo, load_raster


def test_load_raster_round_trip(synthetic_raster, tmp_path):
    path = tmp_path / "rt.tif"
    with rasterio.open(
        path, "w",
        driver="GTiff",
        height=synthetic_raster.height,
        width=synthetic_raster.width,
        count=synthetic_raster.count,
        dtype=synthetic_raster.data.dtype,
        crs=synthetic_raster.crs,
        transform=synthetic_raster.transform,
    ) as dst:
        dst.write(synthetic_raster.data)
    info = load_raster(path)
    assert info.width == 50
    assert info.height == 50
    assert info.count == 3
    assert str(info.crs) == "EPSG:32631"
    np.testing.assert_array_equal(info.data, synthetic_raster.data)


def test_bounds_native(synthetic_raster):
    left, bottom, right, top = synthetic_raster.bounds_native()
    assert left == pytest.approx(500_000.0)
    assert right == pytest.approx(500_000.0 + 50 * 0.5)
    assert top == pytest.approx(4_640_000.0)
    assert bottom == pytest.approx(4_640_000.0 - 50 * 0.5)


def test_bounds_wgs84_round_trip_in_degrees(synthetic_raster_wgs84):
    s, w, n, e = synthetic_raster_wgs84.bounds_wgs84()
    # The WGS84 fixture's CRS is already 4326, so bounds should match the
    # affine-derived ones (in degrees, but allowing tiny numerical noise).
    assert -90.0 < s < 90.0
    assert -180.0 < w < 180.0
    assert s < n
    assert w < e
    # Centered roughly on Montpellier.
    center_lon = 0.5 * (w + e)
    center_lat = 0.5 * (s + n)
    assert 3.0 < center_lon < 5.0
    assert 42.0 < center_lat < 45.0


def test_load_raster_one_band(tmp_path):
    arr = np.arange(100, dtype=np.uint8).reshape(1, 10, 10)
    transform = rasterio.transform.from_origin(0.0, 10.0, 1.0, 1.0)
    path = tmp_path / "oneband.tif"
    with rasterio.open(path, "w", driver="GTiff", height=10, width=10,
                       count=1, dtype="uint8", crs="EPSG:32631",
                       transform=transform) as dst:
        dst.write(arr)
    info = load_raster(path)
    assert info.count == 1
    assert info.data.shape == (1, 10, 10)
