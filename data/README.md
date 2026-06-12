# atomizer-text

**OSM semantic overlay pilot for the Atomizer per-pixel token model.**

This bucket is the canonical, read-only data store for the
`atomizer-text` v1 pilot. It contains the raw source imagery, the
metadata, the 3 extracted representative tiles, and the 9 CLI outputs.
**It is not a model — it is reproducible input + output data** for a
small Python tool that lives in the GitHub repo below.

| location | contents |
|---|---|
| GitHub: [`NoeFlandre/atomizer-text`](https://github.com/NoeFlandre/atomizer-text) | the source code, tests, and CLI |
| HF bucket: `buckets/NoeFlandre/atomizer-text` (this dataset) | the data and CLI outputs |

---

## What this pilot does (one-paragraph version)

For a satellite / aerial photo, the pilot queries OpenStreetMap for all
buildings, roads, landuse polygons, etc. inside the photo's bounding
box, maps each feature's raw OSM tags onto one of 10 fixed semantic
categories (residential / office / commercial / industrial / other
building, road, agricultural land, vegetation or park, water, unknown),
paints those categories onto the photo's pixel grid (with a fixed
priority that lets buildings win over landuse on overlaps), and writes
a 3-panel figure, a JSON of summary statistics, and a per-feature
record of raw OSM tags for a future text-embedding step.

The v1 plan, taxonomy rules, rasterization priority, and per-tile
feasibility results are documented in the GitHub README.

---

## Layout of this bucket

```
data/
├── D034-2021_AERIAL_RGBI.zip            4.77 GB  source aerial patches, D034
└── GLOBAL_ALL_MTD.zip                   2.11 GB  source metadata, all departments

sample_tiles/
├── residential.tif                      1.2 MB   Castelnau-le-Lez (suburban houses)
├── office.tif                           1.1 MB   Port Marianne / Antigone (towers)
└── mixed.tif                            1.0 MB   peri-urban fringe SW of center

results/
├── residential/
│   ├── overlay.png                      3-panel figure (RGB / category / RGB + outlines)
│   ├── stats.json                       coverage, category distribution, tag vocabulary
│   └── tag_records.json                 per-feature records for future embedding
├── office/                              (same 3 files)
└── mixed/                               (same 3 files)
```

Everything under `data/` is the unaltered upstream data from
[`IGNF/FLAIR-HUB`](https://huggingface.co/datasets/IGNF/FLAIR-HUB) (the
zips are mirrored from the `data/` directory of that dataset). The two
top-level zips are mirrored here so the pilot can be reproduced without
re-downloading from the original sources.

`sample_tiles/` and `results/` are produced by the v1 pipeline; their
content is fully derivable from `data/` + the code in the GitHub repo.

---

## Per-tile feasibility summary

| tile | coverage | dominant building tag | top non-building tag | vocab size |
|---|---:|---|---|---:|
| `residential` | 17.6% | `building=yes` (no further info) | `wall`, `leisure` | 12 keys / 15 (k,v) pairs |
| `office` | 32.5% | `building=yes` (+ `building:levels=8/9`) | `highway`, `name`, `natural`, `maxspeed`, `amenity` | 46 keys / 93 (k,v) pairs |
| `mixed` | 1.1% | `building=yes` | `highway`, `oneway`, `surface` | 14 keys / 17 (k,v) pairs |

Headline: **the residential-vs-office contrast is not present in OSM
at 0.2 m over Montpellier** — every building in all three tiles is
tagged `building=yes` (a generic "yes, this is a building" stamp with
no type information). The discriminative signal in the office tile is
its road network and amenity tags, not its building types. See the
GitHub README's "Results & interpretation" section for the full
feasibility write-up.

---

## Reproducing these results from scratch

You need: Python 3.12+, [`uv`](https://docs.astral.sh/uv/), the
[`huggingface-cli`](https://huggingface.co/docs/huggingface_hub/guides/cli)
(`hf` command), and outbound HTTPS access to Overpass (one-shot).

```bash
# 1. Clone the code.
git clone https://github.com/NoeFlandre/atomizer-text.git
cd atomizer-text

# 2. Install dependencies (creates .venv).
uv sync

# 3. Mirror the bucket locally so the source zips are present
#    without hitting the public IGNF/FLAIR-HUB dataset.
hf sync hf://buckets/NoeFlandre/atomizer-text ./bucket

# 4. Re-extract the 3 sample tiles into data/sample_tiles/. The
#    script downloads the zips to a temp dir under data/, picks
#    the 3 patches nearest to the LANDMARKS in the script, and
#    cleans up the temp dir.
ATOMIZER_BUCKET=buckets/NoeFlandre/atomizer-text \
    uv run python scripts/fetch_sample_tiles.py

# 5. Run the CLI on each tile. The default Overpass fetcher hits
#    the public API (~10 s per tile on the first run).
for tile in residential office mixed; do
    uv run python -m atomizer_osm_pilot.cli \
        --raster data/sample_tiles/$tile.tif \
        --out-dir results/$tile \
        --osm-tags building,highway,landuse,shop,office,amenity,natural,waterway,leisure
done
```

After step 5, `results/{residential,office,mixed}/` should be
byte-identical (up to PNG encoder nondeterminism in matplotlib) to the
files in this bucket.

For a fully offline, no-Overpass smoke test, use the included
`scripts/offline_fetcher.py`:

```bash
uv run python -m atomizer_osm_pilot.cli \
    --raster tests/fixtures/tiny.tif \
    --out-dir /tmp/atomizer_offline \
    --fetcher scripts.offline_fetcher:offline_fetcher
```

---

## Tests (offline, no Overpass)

```bash
uv run pytest
```

Expected: 38 passed, 1 skipped (the real-Overpass test, marked
`@pytest.mark.network`).

---

## License and attribution

- The two top-level zips (`data/D034-2021_AERIAL_RGBI.zip` and
  `data/GLOBAL_ALL_MTD.zip`) are mirrored from
  [`IGNF/FLAIR-HUB`](https://huggingface.co/datasets/IGNF/FLAIR-HUB).
  See that dataset card for the upstream license (BD ORTHO imagery
  comes from IGN's open-license policy; the metadata is published by
  IGN under an open license).
- The `sample_tiles/` and `results/` directories are produced by
  this pilot; they are released under the MIT license (same as the
  GitHub repo).
- OpenStreetMap data queried at runtime by the CLI is (c) OpenStreetMap
  contributors, licensed under the
  [ODbL](https://www.openstreetmap.org/copyright).

## Citation

If you use this dataset, please cite the upstream FlairHUB paper:

```bibtex
@article{GARIOUD2026271,
  title  = {FLAIR-HUB: Large-scale multimodal dataset for land cover and crop mapping},
  author = {Garioud, Anatol and Giordano, S{\'e}bastien and David, Nicolas and Gonthier, Nicolas},
  journal= {ISPRS Journal of Photogrammetry and Remote Sensing},
  volume = {237},
  pages  = {271--300},
  year   = {2026},
  doi    = {10.1016/j.isprsjprs.2026.04.017}
}
```

And the Atomizer paper the pilot is designed to inform:

```bibtex
@misc{atomizer2025,
  title  = {Atomizer: a Foundational Model for Remote Sensing},
  author = {anonymous},
  year   = {2025},
  eprint = {2506.13542},
  archivePrefix = {arXiv}
}
```
