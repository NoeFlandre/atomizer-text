"""Environment hardening for PROJ / rasterio.

Some macOS setups export ``PROJ_DATA`` (and/or ``PROJ_LIB``) to an
Anaconda install whose ``proj.db`` is too old for the venv's PROJ library.
That causes ``CRSError: The EPSG code is unknown`` at the first CRS lookup.
The functions here detect the venv's own PROJ data and force-overwrite the
env vars to point there.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _find_proj_data() -> tuple[Path, Path] | None:
    """Locate ``rasterio/proj_data`` and ``pyproj/proj_dir/share/proj`` for
    the venv currently executing this code.
    """
    # ``rasterio`` is a hard dependency of this package, so its
    # ``__file__`` is a reliable anchor: the venv's site-packages is two
    # levels up.
    try:
        import rasterio  # type: ignore
    except Exception:
        return None
    sp = Path(rasterio.__file__).resolve().parent.parent  # site-packages
    rasterio_proj = sp / "rasterio" / "proj_data"
    pyproj_share = sp / "pyproj" / "proj_dir" / "share" / "proj"
    if rasterio_proj.exists() and pyproj_share.exists():
        return rasterio_proj, pyproj_share
    return None


def fix_proj_env() -> bool:
    """Force the PROJ env vars to the venv's own data. Returns True on success."""
    paths = _find_proj_data()
    if paths is None:
        return False
    rasterio_proj, pyproj_share = paths
    os.environ["PROJ_DATA"] = str(rasterio_proj)
    os.environ["PROJ_LIB"] = str(pyproj_share)
    os.environ["PROJ_NETWORK"] = "OFF"
    return True


# Apply at module import time so any subsequent ``import rasterio`` (which
# transitively happens when the package ``__init__`` runs) sees the fixed
# env. Idempotent.
fix_proj_env()


