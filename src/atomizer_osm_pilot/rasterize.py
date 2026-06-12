"""Rasterize categorized OSM features onto an image's pixel grid.

Burn order is governed by :data:`atomizer_osm_pilot.taxonomy.RASTER_PRIORITY`
(Amendment 1): features with higher priority are rasterized last and win on
overlap.
"""
from __future__ import annotations

from typing import Tuple

import geopandas as gpd
import numpy as np
import rasterio.features

from atomizer_osm_pilot.raster_io import RasterInfo
from atomizer_osm_pilot.taxonomy import (
    RASTER_PRIORITY,
    Category,
    map_tags_to_category,
)


def rasterize_features(
    gdf: gpd.GeoDataFrame,
    raster_info: RasterInfo,
) -> Tuple[np.ndarray, np.ndarray, gpd.GeoDataFrame]:
    """Rasterize features onto ``raster_info``'s pixel grid.

    Returns
    -------
    cat_map : np.ndarray of int, shape (H, W)
        Category id per pixel. ``0`` (= :attr:`Category.UNKNOWN`) means no
        feature overlapped the pixel.
    cov_map : np.ndarray of bool, shape (H, W)
        ``True`` wherever any feature overlapped the pixel.
    gdf_out : gpd.GeoDataFrame
        The input features reprojected into ``raster_info.crs`` and
        augmented with two columns:

        - ``category_id`` (int): the assigned :class:`Category` value.
        - ``burn_priority`` (int): the value from :data:`RASTER_PRIORITY`
          used to sort the burn order.
    """
    # Reproject to raster CRS.
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    if str(gdf.crs) != str(raster_info.crs):
        gdf = gdf.to_crs(raster_info.crs)
    gdf = gdf.reset_index(drop=True).copy()

    # Assign category + burn priority per feature.
    gdf["category_id"] = gdf["tags"].apply(
        lambda t: int(map_tags_to_category(t if isinstance(t, dict) else {}))
    )
    gdf["burn_priority"] = gdf["category_id"].apply(
        lambda cid: RASTER_PRIORITY.get(Category(cid), 0)
    )

    # Drop empty geometries to keep rasterize happy.
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()].copy()
    if gdf.empty:
        cat_map = np.zeros((raster_info.height, raster_info.width),
                           dtype=np.int32)
        cov_map = np.zeros_like(cat_map, dtype=bool)
        return cat_map, cov_map, gdf

    # Sort by burn_priority ascending so higher priority overwrites lower.
    gdf = gdf.sort_values("burn_priority", kind="stable").reset_index(drop=True)

    shapes = [(geom, int(cid)) for geom, cid in
              zip(gdf.geometry, gdf["category_id"])]
    cat_map = rasterio.features.rasterize(
        shapes=shapes,
        out_shape=(raster_info.height, raster_info.width),
        transform=raster_info.transform,
        fill=0,
        dtype="int32",
        all_touched=False,
    )
    cov_map = cat_map != 0
    return cat_map, cov_map, gdf
