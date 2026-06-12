"""Raster I/O: load a GeoTIFF into a small RasterInfo dataclass.

TODO(extension point): add an imagery fetcher (WMS/WMTS/IGN) here in a future
version. Out of scope for v1 — assume the user provides a local GeoTIFF.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import numpy as np
import rasterio
from rasterio.transform import Affine
from rasterio.warp import transform_bounds


@dataclass
class RasterInfo:
    """A small view of an opened raster.

    Attributes
    ----------
    data : np.ndarray
        Array of shape (bands, height, width).
    transform : rasterio.Affine
        Affine transform mapping pixel -> CRS coordinates.
    crs : str
        CRS identifier (e.g. ``"EPSG:32631"``).
    width, height, count : int
        Raster dimensions and band count.
    """

    data: np.ndarray
    transform: Affine
    crs: str
    width: int
    height: int
    count: int

    def bounds_native(self) -> Tuple[float, float, float, float]:
        """Return ``(left, bottom, right, top)`` in the raster's native CRS."""
        with rasterio.io.MemoryFile() as _:
            pass
        t = self.transform
        left = t.c
        top = t.f
        right = t.c + t.a * self.width
        bottom = t.f + t.e * self.height
        # Normalize (bottom < top in north-up convention).
        return (left, min(bottom, top), right, max(bottom, top))

    def bounds_wgs84(self) -> Tuple[float, float, float, float]:
        """Return ``(south, west, north, east)`` in EPSG:4326.

        The OSM/Overpass world is WGS84, so callers fetching OSM features
        always want this form.
        """
        left, bottom, right, top = self.bounds_native()
        west, south, east, north = transform_bounds(
            self.crs, "EPSG:4326", left, bottom, right, top
        )
        return (south, west, north, east)


def load_raster(path: str | Path) -> RasterInfo:
    """Read all bands of a GeoTIFF into a single ``(bands, H, W)`` array.

    Parameters
    ----------
    path : str | Path
        Path to a GeoTIFF readable by rasterio.
    """
    with rasterio.open(path) as src:
        data = src.read()  # (count, height, width)
        transform = src.transform
        crs = str(src.crs)
        return RasterInfo(
            data=data,
            transform=transform,
            crs=crs,
            width=src.width,
            height=src.height,
            count=src.count,
        )
