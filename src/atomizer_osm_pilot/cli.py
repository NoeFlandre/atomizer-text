"""CLI entry point for the OSM semantic overlay pilot."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

from atomizer_osm_pilot.osm_fetch import fetch_features
from atomizer_osm_pilot.raster_io import load_raster
from atomizer_osm_pilot.rasterize import rasterize_features
from atomizer_osm_pilot.stats import summarize
from atomizer_osm_pilot.tag_records import build_tag_records
from atomizer_osm_pilot.visualize import render_overlay


DEFAULT_OSM_TAGS = "building,highway,landuse,shop,office,amenity,natural,waterway,leisure"


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="atomizer-osm-pilot",
        description=(
            "Rasterize OSM features onto a satellite GeoTIFF and produce "
            "a 3-panel overlay + summary stats."
        ),
    )
    p.add_argument("--raster", required=True, help="Path to input GeoTIFF.")
    p.add_argument("--out-dir", required=True,
                   help="Output directory; created if it doesn't exist.")
    p.add_argument("--osm-tags", default=DEFAULT_OSM_TAGS,
                   help=f"Comma-separated OSM tag keys (default: {DEFAULT_OSM_TAGS}).")
    p.add_argument("--fetcher", default=None,
                   help="Optional Python callable (module:function) to use "
                        "instead of the default Overpass fetcher. Useful "
                        "for tests and offline runs.")
    return p.parse_args(list(argv) if argv is not None else None)


def _resolve_fetcher(name: str | None):
    if not name:
        return None
    mod_name, _, fn_name = name.partition(":")
    if not fn_name:
        fn_name = mod_name.split(".")[-1]
        mod_name = ".".join(mod_name.split(".")[:-1]) or "builtins"
    import importlib
    mod = importlib.import_module(mod_name)
    return getattr(mod, fn_name)


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fetcher = _resolve_fetcher(args.fetcher)

    raster = load_raster(args.raster)
    bbox = raster.bounds_wgs84()
    tag_keys = [t.strip() for t in args.osm_tags.split(",") if t.strip()]

    print(f"Loading raster: {args.raster}")
    print(f"  size: {raster.width}x{raster.height}, bands: {raster.count}, "
          f"crs: {raster.crs}")
    print(f"  bounds WGS84: south={bbox[0]:.6f} west={bbox[1]:.6f} "
          f"north={bbox[2]:.6f} east={bbox[3]:.6f}")

    print(f"Fetching OSM features for tags: {tag_keys}")
    gdf = fetch_features(bbox, tag_keys, fetcher=fetcher)
    print(f"  fetched {len(gdf)} features")

    print("Rasterizing onto pixel grid (priority order: buildings > roads > "
          "landuse > unknown)...")
    cat_map, cov_map, gdf_reproj = rasterize_features(gdf, raster)

    print("Building per-feature tag records...")
    records = build_tag_records(gdf_reproj, cat_map, raster.transform)

    print("Computing summary statistics...")
    stats = summarize(records, cov_map, cat_map)

    overlay_path = out_dir / "overlay.png"
    stats_path = out_dir / "stats.json"
    records_path = out_dir / "tag_records.json"

    print(f"Rendering overlay to {overlay_path}...")
    rgb = raster.data
    render_overlay(rgb, cat_map, gdf_reproj, output_path=overlay_path)

    stats_path.write_text(json.dumps(stats, indent=2))
    records_path.write_text(json.dumps(records, indent=2))

    print("\n=== Summary ===")
    print(f"  coverage: {stats['coverage'] * 100:.1f}%")
    dist = stats["category_distribution"]
    total = sum(dist.values()) or 1
    top = sorted(dist.items(), key=lambda kv: -kv[1])[:3]
    print("  top categories:")
    for name, count in top:
        if name == "UNKNOWN" and count == total:
            continue
        print(f"    {name}: {count} px ({count / total * 100:.1f}%)")
    vocab = stats["tag_vocabulary"]
    print(f"  features with tags: {vocab['n_features']}")
    print(f"  distinct tag keys: {vocab['n_distinct_keys']}")
    print(f"  distinct (key,value) pairs: {vocab['n_distinct_key_values']}")
    print(f"\nWrote: {overlay_path}, {stats_path}, {records_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
