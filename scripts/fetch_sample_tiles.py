"""One-off data-prep: extract 3 named FlairHUB aerial patches from D034
(Hérault, Montpellier) into ``data/sample_tiles/``.

This script is **explicitly out of the TDD / pytest scope** (see v1 plan,
Amendment 3).

How it works (storage-conscious):

1. Download the 2.1 GB metadata zip from the bucket/HF Hub into a temp
   dir, read the GEOM gpkg to find the lon/lat of every D034 patch, and
   pick the 3 patches closest to known Montpellier landmarks
   (residential: Castelnau-le-Lez; office: Port Marianne / Antigone;
   mixed: peri-urban ~5 km outside the city center).
2. Delete the metadata zip to free disk space.
3. Download the 4.7 GB RGBI zip, extract only the 3 chosen patches into
   ``data/sample_tiles/``, then delete the temp dir.
4. Net local footprint: 3 small patches (~1 MB each) under
   ``data/sample_tiles/``. The HF bucket remains the source of truth for
   the full dataset.

Patches are 512x512 @ 0.2m BD ORTHO aerial RGBI imagery (4 bands; the CLI
reads the first 3 bands as RGB).

Usage:

    uv run python scripts/fetch_sample_tiles.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

# Fix PROJ env before any rasterio import (same as cli/tests).
from atomizer_osm_pilot._env import fix_proj_env
fix_proj_env()

from huggingface_hub import hf_hub_download

# Source of truth on Hugging Face.
DATASET_ID = "IGNF/FLAIR-HUB"
# Optional local mirror (e.g. a private bucket populated with `hf sync`).
# If both ``BUCKET_REPO`` and the file exist on it, we use the bucket.
BUCKET_REPO = os.environ.get("ATOMIZER_BUCKET", "buckets/NoeFlandre/atomizer-text")

RGBI_ZIP = "data/D034-2021_AERIAL_RGBI.zip"
MTD_ZIP = "data/GLOBAL_ALL_MTD.zip"

# Landmarks (lon, lat) used to pick the 3 representative patches. These
# correspond to the v1 plan's intent (Amendment 3):
#   - residential: a single-family-house neighborhood (Castelnau-le-Lez)
#   - office: Port Marianne / Antigone business district
#   - mixed: peri-urban ~5 km outside the center
LANDMARKS: dict[str, tuple[float, float]] = {
    "residential": (3.9015, 43.6361),  # Castelnau-le-Lez center
    "office": (3.8980, 43.6085),       # Port Marianne / Antigone
    "mixed": (3.8200, 43.5800),        # peri-urban fringe south-west
}


def _download(local_dir: Path, filename: str) -> Path:
    """Download a file from the bucket if it exists there, else from
    ``IGNF/FLAIR-HUB``. Stores it inside ``local_dir`` (a temp dir).

    Uses ``force_download=True`` to bypass HF's global cache, so a previous
    run that downloaded to a different directory doesn't accidentally
    return a path that no longer exists.
    """
    local_dir.mkdir(parents=True, exist_ok=True)
    last_err: Optional[Exception] = None
    for repo in (BUCKET_REPO, DATASET_ID):
        try:
            p = hf_hub_download(
                repo_id=repo,
                repo_type="dataset",
                filename=filename,
                local_dir=str(local_dir),
                force_download=True,
            )
            pp = Path(p).resolve()
            # Sanity: the file must actually live under our temp dir.
            if not str(pp).startswith(str(local_dir.resolve())):
                raise RuntimeError(
                    f"hf_hub_download returned {pp} which is outside "
                    f"{local_dir.resolve()}; refusing to use it"
                )
            return pp
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    raise RuntimeError(
        f"Could not download {filename} from {BUCKET_REPO} or {DATASET_ID}: "
        f"{last_err}"
    )


def _pick_closest_patch(
    geoms: "list[tuple[str, tuple[float, float]]]",
    target_lon: float,
    target_lat: float,
) -> Optional[str]:
    """Return the patch_id whose center is closest to (target_lon, target_lat)."""
    import math
    best_id: Optional[str] = None
    best_d = math.inf
    for patch_id, (lon, lat) in geoms:
        # rough equirectangular distance, fine for ~km-scale picks
        dx = (lon - target_lon) * math.cos(math.radians(target_lat))
        dy = (lat - target_lat)
        d = dx * dx + dy * dy
        if d < best_d:
            best_d = d
            best_id = patch_id
    return best_id


def _patch_centers(mtd_zip: Path) -> "list[tuple[str, tuple[float, float]]]":
    """Yield (patch_id, (lon, lat)) for every patch in the metadata.

    The GEOM gpkg is shipped in Lambert-93 (EPSG:2154). We reproject to
    WGS84 so the lon/lat is directly comparable to our landmark targets.
    """
    import geopandas as gpd
    out: list[tuple[str, tuple[float, float]]] = []
    with zipfile.ZipFile(mtd_zip) as zf:
        with zf.open("GLOBAL_ALL_MTD/GLOBAL_ALL_MTD_GEOM.gpkg") as f:
            gdf = gpd.read_file(f)
    gdf = gdf[gdf["patch_id"].str.startswith("D034-2021_")].copy()
    # Always reproject to WGS84 for easy lon/lat math.
    gdf = gdf.set_crs("EPSG:2154", allow_override=True).to_crs("EPSG:4326")
    # Project to a local metric CRS (Lambert-93) for accurate centroids.
    metric = gdf.to_crs("EPSG:2154")
    centroids_metric = metric.geometry.centroid
    centroids_ll = centroids_metric.to_crs("EPSG:4326")
    for pid, geom in zip(gdf["patch_id"], centroids_ll):
        out.append((pid, (geom.x, geom.y)))
    return out


def _in_zip_path(patch_id: str) -> str:
    """Translate a ``patch_id`` to the file path inside ``AERIAL_RGBI.zip``.

    ``patch_id`` has the form ``D034-2021_<area>_<row>-<col>``, e.g.
    ``D034-2021_AA-S1-32_1-1``. The in-zip path inserts the
    ``_AERIAL_RGBI_`` modality segment between the domain and the area,
    yielding
    ``D034-2021_AERIAL_RGBI/<area>/D034-2021_AERIAL_RGBI_<area>_<row>-<col>.tif``.
    """
    parts = patch_id.split("_")
    if len(parts) < 3:
        raise ValueError(f"unexpected patch_id format: {patch_id!r}")
    area = parts[1]
    return (
        f"D034-2021_AERIAL_RGBI/{area}/"
        f"D034-2021_AERIAL_RGBI_{area}_{parts[2]}.tif"
    )


def main() -> int:
    out_dir = Path("data/sample_tiles")
    out_dir.mkdir(parents=True, exist_ok=True)

    # We have to be disk-careful: the metadata zip (2.1 GB) and the RGBI
    # zip (4.7 GB) together won't fit in 5 GB of free space. Download them
    # sequentially and clean up after each.
    tmp_path = Path(tempfile.mkdtemp(prefix=".cache_", dir="data"))
    try:
        # --- Phase 1: download metadata, find the 3 patches to extract ---
        print(f"Downloading {MTD_ZIP} ...")
        mtd = _download(tmp_path, MTD_ZIP)
        print(f"  -> {mtd} ({mtd.stat().st_size / 1e6:.1f} MB)")

        print("Reading patch geometry metadata ...")
        centers = _patch_centers(mtd)
        print(f"  {len(centers)} D034 patches loaded")

        # We'll defer the "is this patch in the RGBI zip?" check until
        # we've downloaded the RGBI zip, but the closest-patch search
        # here will still work because any D034 patch is a candidate.
        picks: dict[str, str] = {}
        for label, (lon, lat) in LANDMARKS.items():
            pick = _pick_closest_patch(centers, lon, lat)
            if pick is None:
                print(f"  [WARN] no patch found near {label} ({lon}, {lat})")
                continue
            picks[label] = pick
            for pid, (px, py) in centers:
                if pid == pick:
                    print(f"  {label}: nearest {pick} (centroid {px:.4f}, {py:.4f})")
                    break

        # Free the metadata zip before we download the big one.
        del mtd
        mtd_path = tmp_path / "data" / "GLOBAL_ALL_MTD.zip"
        if mtd_path.exists():
            mtd_path.unlink()
        gc.collect() if False else None  # best-effort

        # --- Phase 2: download RGBI zip and extract the picked patches ---
        print(f"\nDownloading {RGBI_ZIP} ...")
        rgbi = _download(tmp_path, RGBI_ZIP)
        print(f"  -> {rgbi} ({rgbi.stat().st_size / 1e6:.1f} MB)")

        with zipfile.ZipFile(rgbi) as zf:
            available = {n for n in zf.namelist() if n.endswith(".tif")}
            zip_areas = {n.split("/")[1] for n in available if "/" in n}
            print(f"  {len(available)} .tif members across {len(zip_areas)} areas")

            for label, pick in picks.items():
                member = _in_zip_path(pick)
                if member not in available:
                    print(f"  [WARN] {label}: {pick!r} not in zip; skipping")
                    continue
                print(f"  {label}: extracting {member}")
                with zf.open(member) as src, \
                        (out_dir / f"{label}.tif").open("wb") as dst:
                    shutil.copyfileobj(src, dst)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)

    # Re-list outputs (the temp dir is gone, but the extracted files remain).
    extracted = sorted(out_dir.glob("*.tif"))
    if not extracted:
        print("ERROR: no tiles were extracted.", file=sys.stderr)
        return 1
    print(f"\nDone. Tiles in {out_dir.resolve()}/:")
    total_mb = 0.0
    for p in extracted:
        mb = p.stat().st_size / 1e6
        total_mb += mb
        print(f"  {p.name}  {mb:.1f} MB")
    print(f"  total: {total_mb:.1f} MB (local on-disk)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
