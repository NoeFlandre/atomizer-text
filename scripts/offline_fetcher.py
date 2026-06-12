"""Helper module: a fake fetcher that returns a small synthetic GeoDataFrame
in the bbox of the input tile. Use with the CLI's ``--fetcher`` flag for
offline smoke tests:

    uv run python -m atomizer_osm_pilot.cli \
        --raster tests/fixtures/tiny.tif \
        --out-dir /tmp/atomizer_offline \
        --fetcher scripts.offline_fetcher:offline_fetcher
"""
from __future__ import annotations

import os
from pathlib import Path

from atomizer_osm_pilot._env import fix_proj_env
fix_proj_env()

import geopandas as gpd
from shapely.geometry import LineString, box


def offline_fetcher(bbox_wgs84, tag_keys):
    """Return a small hand-placed GDF inside ``bbox_wgs84``.

    The geometry is purely synthetic and is intended only for offline
    smoke tests of the CLI / visualization pipeline.
    """
    south, west, north, east = bbox_wgs84
    cx = 0.5 * (west + east)
    cy = 0.5 * (south + north)
    dx = (east - west) * 0.30  # 30% of bbox width
    dy = (north - south) * 0.20

    building = box(cx - dx, cy - dy, cx - dx * 0.2, cy + dy * 0.5)
    office = box(cx + dx * 0.1, cy - dy, cx + dx * 0.9, cy + dy * 0.2)
    road = LineString([(west, cy), (east, cy)]).buffer(dx * 0.05)
    park = box(cx - dx * 0.1, cy + dy * 0.4, cx + dx, cy + dy * 0.9)

    gdf = gpd.GeoDataFrame(
        {
            "osmid": ["b-1", "o-1", "r-1", "p-1"],
            "tags": [
                {"building": "house"},
                {"building": "office"},
                {"highway": "residential"},
                {"leisure": "park"},
            ],
        },
        geometry=[building, office, road, park],
        crs="EPSG:4326",
    )
    return gdf
