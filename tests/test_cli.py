"""Integration smoke test for the CLI entry point."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from atomizer_osm_pilot.cli import main


def test_cli_writes_all_outputs(tmp_path, tiny_tif_path, monkeypatch):
    # Run from the project root so the ``scripts.offline_fetcher`` import works.
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    # Make the project root importable for the ``--fetcher`` dotted path.
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))

    out_dir = tmp_path / "out"
    rc = main([
        "--raster", str(tiny_tif_path),
        "--out-dir", str(out_dir),
        "--fetcher", "scripts.offline_fetcher:offline_fetcher",
    ])
    assert rc == 0
    assert (out_dir / "overlay.png").exists()
    assert (out_dir / "stats.json").exists()
    assert (out_dir / "tag_records.json").exists()

    stats = json.loads((out_dir / "stats.json").read_text())
    assert "coverage" in stats
    assert "category_distribution" in stats
    assert "tag_vocabulary" in stats
    assert stats["coverage"] >= 0.0
