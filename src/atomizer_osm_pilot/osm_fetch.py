"""OSM feature fetching (Overpass wrapper).

This is the only module in the package that talks to the network. Tests
inject a fake ``fetcher`` callable (see :func:`fake_fetcher` in
``tests/conftest.py``) so the suite runs fully offline.
"""
from __future__ import annotations

import math
from typing import Callable, Iterable, Tuple

import geopandas as gpd


Fetcher = Callable[[Tuple[float, float, float, float], Iterable[str]],
                   gpd.GeoDataFrame]


def _is_nan(x) -> bool:
    try:
        return isinstance(x, float) and math.isnan(x)
    except Exception:
        return False


def _default_fetcher(bbox_wgs84: Tuple[float, float, float, float],
                     tag_keys: Iterable[str]) -> gpd.GeoDataFrame:
    """Default fetcher: a thin wrapper around ``osmnx.features.features_from_bbox``.

    ``bbox_wgs84`` is ``(south, west, north, east)`` in EPSG:4326.

    The OSMnx API has shifted between versions: newer releases expose
    ``osmnx.features.features_from_bbox``; older ones expose
    ``osmnx.features_from_bbox``. We try the modern name first and fall
    back to the legacy one.
    """
    import osmnx
    bbox = (bbox_wgs84[1], bbox_wgs84[0], bbox_wgs84[3], bbox_wgs84[2])
    tags = {key: True for key in tag_keys}

    fn = getattr(osmnx.features, "features_from_bbox", None) \
        or getattr(osmnx, "features_from_bbox", None)
    if fn is None:
        raise RuntimeError(
            "osmnx does not expose features_from_bbox; please install "
            "osmnx>=1.2 or inject a fetcher explicitly."
        )
    gdf = fn(bbox=bbox, tags=tags)
    # Normalize tags. osmnx 2.x flattens OSM tags into individual columns
    # of the GeoDataFrame; older versions / Overpass returned a single
    # ``tags`` column containing the dict. Rebuild a per-row tags dict
    # in either case.
    if "tags" in gdf.columns and isinstance(gdf["tags"].iloc[0], dict):
        tags_series = gdf["tags"]
    else:
        skip = {"geometry", "osmid", "element_type", "nodes"}
        cols = [c for c in gdf.columns if c not in skip]
        tags_series = gdf[cols].apply(
            lambda row: {c: row[c] for c in cols
                         if row[c] is not None and not _is_nan(row[c])},
            axis=1,
        )
    gdf = gdf.assign(tags=tags_series.values)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")
    return gdf.reset_index(drop=True)


def fetch_features(
    bbox_wgs84: Tuple[float, float, float, float],
    tag_keys: Iterable[str],
    *,
    fetcher: Fetcher | None = None,
) -> gpd.GeoDataFrame:
    """Fetch OSM features intersecting a WGS84 bounding box.

    Parameters
    ----------
    bbox_wgs84 : (south, west, north, east)
        Bounding box in EPSG:4326.
    tag_keys : iterable of str
        OSM tag keys to query (e.g. ``["building", "highway", "landuse"]``).
    fetcher : callable, optional
        Injectable fetcher for tests. If ``None``, uses
        :func:`_default_fetcher` which hits the Overpass API via osmnx.
    """
    fn = fetcher if fetcher is not None else _default_fetcher
    gdf = fn(bbox_wgs84, tag_keys)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf
