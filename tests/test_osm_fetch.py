"""Tests for osm_fetch.fetch_features (with injectable fetcher; offline)."""
from __future__ import annotations

import geopandas as gpd
import pytest

from atomizer_osm_pilot.osm_fetch import fetch_features


# Only the real-Overpass test is marked network; the rest must run offline.
@pytest.mark.network
@pytest.mark.skip(reason="network tests are skipped by default; run with -m network")
def test_real_overpass_returns_geodataframe():
    # Tiny bbox in central Paris (Châtelet), well-tagged area.
    bbox = (48.855, 2.345, 48.860, 2.350)
    gdf = fetch_features(bbox, ["building"])
    assert isinstance(gdf, gpd.GeoDataFrame)
    assert len(gdf) > 0
    assert "tags" in gdf.columns


def test_fetch_features_uses_injected_fetcher(synthetic_raster, fake_fetcher):
    bbox = (43.5, 3.8, 43.7, 4.0)
    gdf = fetch_features(bbox, ["building"], fetcher=fake_fetcher)
    assert isinstance(gdf, gpd.GeoDataFrame)
    assert len(gdf) == 5
    assert str(gdf.crs) == "EPSG:4326"


def test_fetch_features_passes_bbox_and_tags_to_fetcher(synthetic_raster):
    seen = {}

    def _f(bbox, tag_keys):
        seen["bbox"] = bbox
        seen["tags"] = list(tag_keys)
        return gpd.GeoDataFrame({"tags": [], "geometry": []}, crs="EPSG:4326")

    bbox = (0.0, 0.0, 1.0, 1.0)
    tags = ["building", "highway"]
    fetch_features(bbox, tags, fetcher=_f)
    assert seen["bbox"] == bbox
    assert seen["tags"] == tags
