"""OSM Semantic Overlay Pilot.

A small, well-tested feasibility tool that loads a satellite GeoTIFF, fetches
overlapping OSM features, maps raw OSM tags to a small human-defined semantic
taxonomy, rasterizes that taxonomy onto the image's pixel grid, and produces
stats + a 3-panel figure.

This is v1: no embeddings, no training, no image fetching.
"""

# IMPORTANT: fix the PROJ env vars before any module that imports
# rasterio/pyproj. Doing this at the top of __init__.py guarantees it
# runs before any submodule's imports.
from atomizer_osm_pilot import _env  # noqa: F401  (side effect)

from atomizer_osm_pilot.raster_io import RasterInfo, load_raster
from atomizer_osm_pilot.taxonomy import (
    CATEGORIES,
    Category,
    RASTER_PRIORITY,
    RULES,
    map_tags_to_category,
)
from atomizer_osm_pilot.osm_fetch import fetch_features
from atomizer_osm_pilot.rasterize import rasterize_features
from atomizer_osm_pilot.tag_records import build_tag_records
from atomizer_osm_pilot.stats import (
    category_distribution,
    compute_coverage,
    summarize,
    tag_vocabulary,
)
from atomizer_osm_pilot.visualize import render_overlay

__all__ = [
    "RasterInfo",
    "load_raster",
    "Category",
    "CATEGORIES",
    "RULES",
    "RASTER_PRIORITY",
    "map_tags_to_category",
    "fetch_features",
    "rasterize_features",
    "build_tag_records",
    "compute_coverage",
    "category_distribution",
    "tag_vocabulary",
    "summarize",
    "render_overlay",
]
