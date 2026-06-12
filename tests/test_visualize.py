"""Tests for visualize.render_overlay."""
from __future__ import annotations

import geopandas as gpd
import numpy as np
from shapely.geometry import box

from atomizer_osm_pilot.taxonomy import Category
from atomizer_osm_pilot.visualize import CATEGORY_COLORS, render_overlay


def test_render_overlay_returns_figure_with_three_axes(synthetic_raster):
    gdf = gpd.GeoDataFrame({"tags": [], "geometry": []}, crs="EPSG:32631")
    cat_map = np.zeros((synthetic_raster.height, synthetic_raster.width),
                       dtype=np.int32)
    fig = render_overlay(synthetic_raster.data, cat_map, gdf)
    assert len(fig.axes) == 3
    import matplotlib.pyplot as plt
    plt.close(fig)


def test_render_overlay_writes_png(synthetic_raster, tmp_path):
    gdf = gpd.GeoDataFrame({"tags": [], "geometry": []}, crs="EPSG:32631")
    cat_map = np.zeros((synthetic_raster.height, synthetic_raster.width),
                       dtype=np.int32)
    out = tmp_path / "overlay.png"
    render_overlay(synthetic_raster.data, cat_map, gdf, output_path=out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_category_colors_keys_match_categories():
    for c in Category:
        assert c in CATEGORY_COLORS
