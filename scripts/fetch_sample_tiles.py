"""One-off data-prep: download 3 named FlairHUB aerial patches from D034
(Hérault, Montpellier) into ``data/sample_tiles/``.

This script is **explicitly out of the TDD / pytest scope** (see v1 plan,
Amendment 3). It uses the standard ``huggingface_hub`` client; if a chosen
patch is unavailable, the script falls back to a documented alternative in
the same domain.

Patches are 512x512 @ 0.2m, BD ORTHO aerial RGBI imagery (4 bands; we'll
keep the RGBI tif as-is — the CLI will read the first 3 bands).

The three target tiles are chosen to maximize category diversity for the
feasibility pilot:

- ``residential``: a single-family-house neighborhood in a Castelnau-le-Lez
  suburb; expected to be dominated by ``RESIDENTIAL_BUILDING`` + ``ROAD``.
- ``office``: a Port Marianne / Antigone business-district patch;
  expected to contain ``OFFICE_BUILDING`` / ``COMMERCIAL_BUILDING`` +
  ``ROAD``.
- ``mixed``: a peri-urban patch with buildings, roads, and farmland /
  green space; expected to exercise ``AGRICULTURAL_LAND`` /
  ``VEGETATION_OR_PARK`` and the building-over-landuse overlap case
  (Amendment 1 of the v1 plan).

Usage:

    uv run python scripts/fetch_sample_tiles.py

If a specific patch filename does not exist in D034's AERIAL_RGBI_IMS zip
the script will print a clear error and exit non-zero. Update the
``TARGETS`` dict with the actual patch ids you find by listing
``data/D034-2021_AERIAL_RGBI_IMS.zip``'s contents.
"""
from __future__ import annotations

import os
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Iterable

# Fix PROJ env before any rasterio import (same as cli/tests).
from atomizer_osm_pilot._env import fix_proj_env
fix_proj_env()

from huggingface_hub import hf_hub_download

DATASET_ID = "IGNF/FLAIR-HUB"

# D034 = Hérault (Montpellier), AERIAL RGBI (4-band BD ORTHO), 512x512 @ 0.2m.
DOMAIN_ZIP = "data/D034-2021_AERIAL_RGBI.zip"

# Each entry maps a logical tile name to a list of candidate patch filenames
# (relative paths inside the zip). The first that exists wins.
TARGETS: dict[str, list[str]] = {
    "residential": [
        "D034-2021/castelnau_residential_001.tif",
        "D034-2021/castelnau_residential_002.tif",
    ],
    "office": [
        "D034-2021/antigone_office_001.tif",
        "D034-2021/port_marianne_office_001.tif",
    ],
    "mixed": [
        "D034-2021/periurban_mixed_001.tif",
        "D034-2021/periurban_mixed_002.tif",
    ],
}


def _list_zip_members(zf: zipfile.ZipFile) -> set[str]:
    return {n for n in zf.namelist() if n.lower().endswith(".tif")}


def _pick_first(member_candidates: Iterable[str], available: set[str]) -> str | None:
    for c in member_candidates:
        if c in available:
            return c
    return None


def main() -> int:
    out_dir = Path("data/sample_tiles")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {DOMAIN_ZIP} from {DATASET_ID} ...")
    zip_path = hf_hub_download(
        repo_id=DATASET_ID,
        repo_type="dataset",
        filename=DOMAIN_ZIP,
        local_dir=".",
    )
    zip_path = Path(zip_path)
    print(f"  -> {zip_path} ({zip_path.stat().st_size / 1e6:.1f} MB)")

    with zipfile.ZipFile(zip_path) as zf:
        members = _list_zip_members(zf)
        print(f"  zip contains {len(members)} .tif members")

        any_ok = False
        for name, candidates in TARGETS.items():
            chosen = _pick_first(candidates, members)
            if chosen is None:
                print(
                    f"  [WARN] none of the {name!r} candidates were found in "
                    f"the zip. Available samples: "
                    f"{sorted(members)[:5]} ..."
                )
                continue
            print(f"  extracting {name!r} -> {chosen}")
            with zf.open(chosen) as src, (out_dir / f"{name}.tif").open("wb") as dst:
                shutil.copyfileobj(src, dst)
            any_ok = True

    if not any_ok:
        print("ERROR: no tiles were extracted. Update TARGETS with real "
              "patch filenames from this dataset version.", file=sys.stderr)
        return 1

    print(f"Done. Tiles in {out_dir.resolve()}/")
    for p in sorted(out_dir.glob("*.tif")):
        print(f"  {p.name}  {p.stat().st_size / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
