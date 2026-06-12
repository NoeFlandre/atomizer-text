# atomizer-text

OSM semantic overlay pilot for the Atomizer per-pixel token model.

Given a satellite/aerial GeoTIFF, this tool:

1. fetches OpenStreetMap features covering the tile (via Overpass/osmnx);
2. maps each feature's raw OSM tags to a small human-defined semantic
   category (residential / office / commercial / industrial / other
   building, road, agricultural land, vegetation/park, water, unknown);
3. rasterizes those categories onto the image's pixel grid, respecting a
   fixed overlap priority (buildings > roads > landuse > unknown);
4. produces a 3-panel overlay figure (RGB / category map / RGB with OSM
   outlines), a JSON of summary statistics, and a per-feature
   `tag_records.json` for the future embedding step.

This is v1 of a feasibility pilot. It does **not** embed tags, train a
model, or fetch imagery. See the "Results & interpretation" section for
the feasibility questions it is designed to answer.

---

## Setup

This is a [uv](https://docs.astral.sh/uv/) project. From the project
root:

```bash
uv sync                                  # install all deps into .venv
```

The package is an editable install (`atomizer-text`), so all of
`atomizer_osm_pilot` and `scripts/` is importable from the project root.

### Optional: fetch a few real sample tiles (Amendment 3)

To run the CLI on real FlairHUB aerial patches (D034, Hérault /
Montpellier, 512x512 @ 0.2m):

```bash
uv run python scripts/fetch_sample_tiles.py
```

This downloads `D034-2021_AERIAL_RGBI_IMS.zip` from
`IGNF/FLAIR-HUB` on Hugging Face and extracts three named patches into
`data/sample_tiles/{residential,office,mixed}.tif`. The script is a
one-off data-prep utility, **not** part of the test suite.

> The first run downloads the whole domain ZIP (~hundreds of MB). For
> quick exploration the `tests/fixtures/tiny.tif` and the offline
> fetcher in `scripts/offline_fetcher.py` are enough to exercise the
> pipeline without network access.

---

## Running the tests

```bash
uv run pytest
```

Tests run **fully offline** by default. The single real-Overpass smoke
test is marked `@pytest.mark.network` and is skipped; run it explicitly
with:

```bash
uv run pytest -m network
```

Coverage breakdown (as of v1):

| module              | tests | focus                                                  |
|---------------------|-------|--------------------------------------------------------|
| `raster_io`         | 4     | GeoTIFF load, native + WGS84 bounds                    |
| `taxonomy`          | 14    | all categories, edge cases, **`RASTER_PRIORITY` pinning** (Amendment 1) |
| `osm_fetch`         | 3     | injectable fetcher (real-network test skipped by default) |
| `rasterize`         | 5     | empty GDF, full coverage, **building-over-landuse**, **road-over-landuse**, CRS reprojection (Amendment 1) |
| `tag_records`       | 3     | empty input, multi-feature, raw-tags not mutated       |
| `stats`             | 5     | coverage, distribution, vocabulary, summarize          |
| `visualize`         | 3     | 3-panel figure, PNG output, deterministic colors       |
| `cli`               | 1     | end-to-end smoke test against `tiny.tif` + offline fetcher |

---

## CLI usage

```bash
uv run python -m atomizer_osm_pilot.cli \
    --raster data/sample_tiles/residential.tif \
    --out-dir results/residential \
    --osm-tags building,highway,landuse,shop,office,amenity,natural,waterway,leisure
```

The CLI writes three files into `--out-dir`:

- `overlay.png` — the 3-panel figure (RGB / category map / RGB + outlines).
- `stats.json` — coverage %, per-category pixel counts, and a tag-vocabulary
  summary (number of distinct tag keys and `key=value` pairs, top keys).
- `tag_records.json` — per-feature records
  (`{feature_id, category, category_id, raw_tags, pixel_count, centroid_xy}`)
  ready for the future embedding step.

A short human-readable summary is printed to stdout.

### Offline mode

For testing without Overpass, pass an injectable fetcher:

```bash
uv run python -m atomizer_osm_pilot.cli \
    --raster tests/fixtures/tiny.tif \
    --out-dir /tmp/atomizer_offline \
    --fetcher scripts.offline_fetcher:offline_fetcher
```

`scripts/offline_fetcher.py` returns a small hand-placed synthetic GDF
inside the raster's bounding box.

---

## Architecture

```
src/atomizer_osm_pilot/
├── __init__.py        # public API; forces PROJ env hardening
├── _env.py            # PROJ env hardening (macOS Anaconda workaround)
├── raster_io.py       # RasterInfo dataclass + load_raster()
├── osm_fetch.py       # fetch_features(bbox, tag_keys, fetcher=None)
├── taxonomy.py        # Category enum, RULES list, RASTER_PRIORITY, map_tags_to_category
├── rasterize.py       # rasterize_features() using RASTER_PRIORITY burn order
├── tag_records.py     # build_tag_records() for the future embedding step
├── stats.py           # coverage, category distribution, tag vocabulary
├── visualize.py       # render_overlay(): 3-panel figure
└── cli.py             # argparse entry point + summary printing
```

### Priority ordering (Amendment 1)

When two OSM features overlap on the same pixel, the higher-priority one
wins. Priority is **not** derived from the `Category` enum value (those
are display/serialization only). The explicit mapping lives in
`taxonomy.RASTER_PRIORITY`:

| priority | categories                                                         |
|---------:|--------------------------------------------------------------------|
| 0        | `UNKNOWN` (no feature / no rule match)                             |
| 1        | `AGRICULTURAL_LAND`, `VEGETATION_OR_PARK`, `WATER`                 |
| 2        | `ROAD`                                                             |
| 3        | all building categories                                            |

`rasterize_features` sorts features by `RASTER_PRIORITY[category]`
ascending before calling `rasterio.features.rasterize`, so higher
priorities overwrite lower ones. This is pinned by a unit test
(`test_raster_priority_ordering_buildings_win`) and exercised by two
explicit overlap tests
(`test_rasterize_building_wins_over_landuse_overlap`,
`test_rasterize_road_wins_over_landuse_overlap`).

### Editing the taxonomy

`taxonomy.RULES` is the single source of truth for tag-to-category
mapping. Add or reorder rules there to iterate; the rasterize and CLI
will pick up changes automatically. The mapping is data-driven
(`Rule(name, matches, category)`), so iteration does not require
touching call sites.

---

## Results & interpretation

This pilot is designed to answer three feasibility questions before any
embedding/training work starts. For each of the three sample tiles
(`residential`, `office`, `mixed`):

1. **At what image resolution does a pixel correspond to something OSM
   can meaningfully label?** The FlairHUB BD ORTHO patches are 512x512
   @ 0.2m (≈ 100 m on a side). Inspect the
   `category_distribution` — a tile dominated by `UNKNOWN` with
   `coverage < 10%` suggests OSM is sparse there; values >70% with a
   healthy mix of `RESIDENTIAL_BUILDING` + `ROAD` suggest a pixel often
   corresponds to a single labeled entity.

2. **How dense, clean, and diverse is OSM tagging in the study area?**
   Look at `tag_vocabulary` and the per-feature `raw_tags` in
   `tag_records.json`:
   - `n_distinct_keys` / `n_distinct_key_values` estimates the size of
     the embedding vocabulary you would need.
   - A high fraction of `building=*` values being just `"yes"` (no
     `building:use`, no `office`, no `shop`) means the residential vs.
     office distinction **cannot be learned from OSM alone** in this
     area; you'd need either richer OSM coverage or a different signal
     (e.g. address points, BD TOPO).
   - Compare `residential` vs `office` tiles: if both have
     comparable `n_distinct_keys` but the `office` tile has very few
     `OFFICE_BUILDING` pixels, the contrast the whole project depends
     on is missing in OSM at this resolution.

3. **Can we build a clean, reusable per-pixel tag map by rasterizing
   OSM onto the image grid?** Inspect `overlay.png` and the
   `category_distribution`. Success looks like: pixel-aligned polygons,
   no obvious mis-alignment between visible buildings in the RGB panel
   and the OSM outlines in the third panel, and the building-over-
   landuse overlap case (Amendment 1) showing buildings winning where
   they should.

If the residential and office tiles both look healthy but are
indistinguishable in their `tag_vocabulary` (i.e. the OSM tags don't
carry the residential/office signal at this resolution), the
feasibility answer is "no, not in this area with this dataset" and the
next step is to either (a) look for richer OSM-derived sources (e.g.
BD TOPO `usage_1` / `usage_2`), or (b) move to a different study area
with finer-grained building tags (e.g. parts of Germany, where
`building=residential` / `building=apartments` is consistently used).

---

## Out of scope (v1)

- No embedding model, no Atomizer training, no reconstruction loss.
- No WMS/WMTS/IGN imagery fetching. A clearly marked TODO in
  `raster_io.py` notes this as an extension point.
- No multi-temporal handling.
- No web UI. CLI only.
- Taxonomy is data-driven (`taxonomy.RULES`) but not yet YAML-loaded.

## File map (output of `find`)

```
atomizer-text/
├── pyproject.toml
├── README.md                          (this file)
├── src/atomizer_osm_pilot/            (8 modules, ~600 LOC)
├── tests/                             (8 test files, 38 tests, all offline)
├── scripts/
│   ├── fetch_sample_tiles.py          (Amendment 3, not in pytest)
│   └── offline_fetcher.py             (synthetic fetcher for the CLI)
└── data/sample_tiles/                 (gitignored; populated by fetch_sample_tiles.py)
```
