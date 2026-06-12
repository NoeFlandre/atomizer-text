"""3-panel overlay visualization: RGB / categorical map / RGB + OSM outlines."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Tuple

import geopandas as gpd
import matplotlib
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import numpy as np

matplotlib.use("Agg")  # headless-safe default; override by importing pyplot

import matplotlib.pyplot as plt

from atomizer_osm_pilot.taxonomy import CATEGORIES, Category


# Fixed, stable colors per category so legends stay consistent across runs.
CATEGORY_COLORS: dict[Category, str] = {
    Category.UNKNOWN: "#dddddd",
    Category.RESIDENTIAL_BUILDING: "#e41a1c",
    Category.OFFICE_BUILDING: "#377eb8",
    Category.COMMERCIAL_BUILDING: "#4daf4a",
    Category.INDUSTRIAL_BUILDING: "#984ea3",
    Category.OTHER_BUILDING: "#ff7f00",
    Category.ROAD: "#ffff33",
    Category.AGRICULTURAL_LAND: "#a65628",
    Category.VEGETATION_OR_PARK: "#1b7837",
    Category.WATER: "#00bfff",
}


def _normalize_rgb(data: np.ndarray) -> np.ndarray:
    """Return an ``(H, W, 3)`` uint8 array from a rasterio read."""
    if data.ndim == 2:
        data = data[np.newaxis, ...]
    if data.shape[0] == 1:
        rgb = np.repeat(data[0:1], 3, axis=0)
    elif data.shape[0] >= 3:
        rgb = data[:3]
    else:
        # e.g. 2-band: pad to 3 by repeating the first band.
        rgb = np.concatenate([data, np.repeat(data[-1:], 3 - data.shape[0],
                                              axis=0)], axis=0)
    # Normalize per-band to 0..255 for display.
    rgb = rgb.astype(np.float32)
    for i in range(rgb.shape[0]):
        band = rgb[i]
        lo, hi = np.percentile(band, [2, 98])
        if hi - lo < 1e-6:
            hi = lo + 1.0
        rgb[i] = np.clip((band - lo) / (hi - lo) * 255.0, 0, 255)
    return np.transpose(rgb, (1, 2, 0)).astype(np.uint8)


def render_overlay(
    rgb: np.ndarray,
    cat_map: np.ndarray,
    gdf: gpd.GeoDataFrame,
    categories: Iterable[Category] = CATEGORIES,
    *,
    output_path: Optional[str | Path] = None,
) -> "matplotlib.figure.Figure":
    """Build a 3-panel overlay figure.

    Parameters
    ----------
    rgb : np.ndarray
        Either ``(bands, H, W)`` (rasterio-style) or ``(H, W, 3)``.
    cat_map : np.ndarray
        Integer ``(H, W)`` category map (0 = unknown).
    gdf : gpd.GeoDataFrame
        OSM features, expected to be in the same CRS as the raster and to
        have a ``category_id`` column.
    categories : iterable of Category
        Ordered list of categories to include in the legend.
    output_path : str or Path, optional
        If given, the figure is saved to this path as PNG.
    """
    cats = tuple(categories)
    rgb_disp = _normalize_rgb(rgb)
    cmap = mcolors.ListedColormap(
        [CATEGORY_COLORS.get(c, "#ffffff") for c in cats],
        name="osm_categories",
    )
    norm = mcolors.BoundaryNorm(
        boundaries=np.arange(-0.5, len(cats) + 0.5, 1.0), ncolors=len(cats)
    )

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    # (a) RGB
    axes[0].imshow(rgb_disp)
    axes[0].set_title("RGB")
    axes[0].axis("off")

    # (b) categorical map
    im = axes[1].imshow(cat_map, cmap=cmap, norm=norm, interpolation="nearest")
    axes[1].set_title("OSM tag map")
    axes[1].axis("off")
    legend_handles = [
        mpatches.Patch(color=CATEGORY_COLORS.get(c, "#ffffff"), label=c.name)
        for c in cats
    ]
    axes[1].legend(handles=legend_handles, bbox_to_anchor=(1.02, 1.0),
                   loc="upper left", fontsize=7, frameon=False)

    # (c) RGB + OSM outlines
    axes[2].imshow(rgb_disp)
    if gdf is not None and len(gdf) > 0 and "category_id" in gdf.columns:
        for _, row in gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            cid = int(row.get("category_id", 0))
            color = CATEGORY_COLORS.get(Category(cid), "#000000")
            try:
                xs, ys = geom.exterior.xy
            except AttributeError:
                xs, ys = geom.xy
            axes[2].plot(xs, ys, color=color, linewidth=1.0)
    axes[2].set_title("RGB + OSM outlines")
    axes[2].axis("off")

    fig.tight_layout()
    if output_path is not None:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
    return fig
