"""Summary statistics: coverage, category distribution, tag vocabulary."""
from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, List

import numpy as np

from atomizer_osm_pilot.taxonomy import CATEGORIES, Category


def compute_coverage(cov_map: np.ndarray) -> float:
    """Return the fraction of pixels overlapped by any tagged feature."""
    if cov_map.size == 0:
        return 0.0
    return float(cov_map.sum()) / float(cov_map.size)


def category_distribution(
    cat_map: np.ndarray,
    categories: Iterable[Category] = CATEGORIES,
) -> Dict[str, int]:
    """Return ``{category.name: pixel_count}`` for the given categories.

    The values sum to ``cat_map.size``; categories with zero pixels are
    included so downstream consumers see the full set.
    """
    flat = cat_map.ravel().astype(np.int64, copy=False)
    counts = {c.name: 0 for c in categories}
    if flat.size == 0:
        return counts
    unique, c_counts = np.unique(flat, return_counts=True)
    cat_by_id = {int(c): c for c in categories}
    for uid, ccount in zip(unique, c_counts):
        cat = cat_by_id.get(int(uid))
        if cat is not None:
            counts[cat.name] = int(ccount)
    return counts


def tag_vocabulary(records: List[dict], top_k: int = 20) -> dict:
    """Summarize the raw OSM tag vocabulary seen across ``records``.

    Returns a dict with:

    - ``n_features`` (int)
    - ``n_distinct_keys`` (int)
    - ``n_distinct_key_values`` (int) — count of distinct ``(key, value)`` pairs
    - ``top_keys`` (list of ``{"key", "count"}``, sorted desc)
    """
    key_counter: Counter = Counter()
    kv_pairs: set = set()
    n_features = 0
    for rec in records or []:
        tags = rec.get("raw_tags") or {}
        if not isinstance(tags, dict):
            continue
        n_features += 1
        for k, v in tags.items():
            if v is None:
                continue
            key_counter[str(k)] += 1
            kv_pairs.add((str(k), str(v)))
    return {
        "n_features": n_features,
        "n_distinct_keys": len(key_counter),
        "n_distinct_key_values": len(kv_pairs),
        "top_keys": [{"key": k, "count": c}
                     for k, c in key_counter.most_common(top_k)],
    }


def summarize(
    records: List[dict],
    cov_map: np.ndarray,
    cat_map: np.ndarray,
    categories: Iterable[Category] = CATEGORIES,
    top_k_vocab: int = 20,
) -> dict:
    """One-call aggregator that returns a single JSON-serializable dict."""
    return {
        "coverage": compute_coverage(cov_map),
        "category_distribution": category_distribution(cat_map, categories),
        "tag_vocabulary": tag_vocabulary(records, top_k=top_k_vocab),
    }
