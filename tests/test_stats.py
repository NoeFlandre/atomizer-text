"""Tests for stats module."""
from __future__ import annotations

import numpy as np

from atomizer_osm_pilot.stats import (
    category_distribution,
    compute_coverage,
    summarize,
    tag_vocabulary,
)
from atomizer_osm_pilot.taxonomy import Category


def test_compute_coverage_empty():
    assert compute_coverage(np.zeros((0, 0), dtype=bool)) == 0.0


def test_compute_coverage_full():
    arr = np.ones((10, 10), dtype=bool)
    assert compute_coverage(arr) == 1.0


def test_category_distribution_sums_to_total():
    cat_map = np.zeros((4, 4), dtype=np.int32)
    cat_map[0:2, 0:2] = int(Category.RESIDENTIAL_BUILDING)
    cat_map[2:4, 0:2] = int(Category.ROAD)
    dist = category_distribution(cat_map)
    assert sum(dist.values()) == 16
    assert dist["RESIDENTIAL_BUILDING"] == 4
    assert dist["ROAD"] == 4
    assert dist["UNKNOWN"] == 8


def test_tag_vocabulary_counts():
    records = [
        {"raw_tags": {"building": "house", "building:use": "residential"}},
        {"raw_tags": {"highway": "residential"}},
        {"raw_tags": {"building": "office"}},
    ]
    v = tag_vocabulary(records)
    assert v["n_features"] == 3
    assert v["n_distinct_keys"] == 3
    assert v["n_distinct_key_values"] == 4
    top = {kv["key"]: kv["count"] for kv in v["top_keys"]}
    assert top["building"] == 2


def test_summarize_is_json_ready():
    cat_map = np.zeros((3, 3), dtype=np.int32)
    cat_map[0, 0] = int(Category.OFFICE_BUILDING)
    records = [{"raw_tags": {"building": "office"}}]
    s = summarize(records, cat_map != 0, cat_map)
    assert "coverage" in s
    assert "category_distribution" in s
    assert "tag_vocabulary" in s
    assert s["coverage"] == 1 / 9
    assert s["tag_vocabulary"]["n_distinct_keys"] == 1
