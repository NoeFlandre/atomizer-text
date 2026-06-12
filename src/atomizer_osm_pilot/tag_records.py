"""Per-feature tag records for the future embedding step (v1: no embedding)."""
from __future__ import annotations

from typing import List

import geopandas as gpd
import numpy as np
import rasterio.features
from rasterio.transform import Affine

from atomizer_osm_pilot.taxonomy import Category, map_tags_to_category


def build_tag_records(
    gdf: gpd.GeoDataFrame,
    cat_map: np.ndarray,
    transform: Affine,
) -> List[dict]:
    """Build a list of per-feature records.

    Each record is a flat dict suitable for JSON serialization:

    - ``feature_id`` (str|int): the OSM id of the feature, or the row index
      if no id is present.
    - ``category`` (str): the category name (e.g. ``"RESIDENTIAL_BUILDING"``).
    - ``category_id`` (int): the enum value.
    - ``raw_tags`` (dict): the original OSM tag dict, untouched.
    - ``pixel_count`` (int): number of pixels in ``cat_map`` that this
      feature rasterizes to.
    - ``centroid_xy`` ([float, float]): the feature's centroid in the
      CRS of ``transform``.

    An empty input GDF returns ``[]``. Empty geometries are skipped (their
    pixel_count is 0 and centroid is ``None``).
    """
    out: List[dict] = []
    if gdf is None or len(gdf) == 0:
        return out

    for idx, row in gdf.iterrows():
        geom = row.geometry
        tags = row.get("tags", {}) or {}
        if not isinstance(tags, dict):
            tags = {}
        category = map_tags_to_category(tags)
        osmid = row.get("osmid", idx)

        if geom is None or geom.is_empty:
            out.append({
                "feature_id": str(osmid),
                "category": category.name,
                "category_id": int(category),
                "raw_tags": dict(tags),
                "pixel_count": 0,
                "centroid_xy": None,
            })
            continue

        # Rasterize this single feature with a unique fill value to count
        # its pixels.
        fill = idx + 1  # unique per row (assuming unique idx)
        single = rasterio.features.rasterize(
            [(geom, fill)],
            out_shape=cat_map.shape,
            transform=transform,
            fill=0,
            dtype="int32",
            all_touched=False,
        )
        pixel_count = int((single == fill).sum())
        centroid = geom.centroid
        out.append({
            "feature_id": str(osmid),
            "category": category.name,
            "category_id": int(category),
            "raw_tags": dict(tags),
            "pixel_count": pixel_count,
            "centroid_xy": [centroid.x, centroid.y],
        })
    return out
