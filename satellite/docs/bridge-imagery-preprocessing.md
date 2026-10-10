# Curated bridge imagery preprocessing

The Routes demo uses small georeferenced PNG files served by FastAPI at `/static`.
PostgreSQL holds completed catalog metadata, observations and review polygons,
never image bytes. Germany, Libya and Nepal share the same catalog and API shape.
Germany also includes regional XYZ tiles and separate Copernicus inundation/flood
trace polygons; see [regional preprocessing](regional-imagery.md).

The checked-in catalog is
`src/floodbeacon/static/imagery/bridge-catalog/catalog.json`. Each case has an
immutable content-derived run ID. Publication validates all image and comparison
checksums before any database operation, and publishes each complete case in one
transaction. Repeating publication skips existing matching run IDs. The catalog
contains original source URLs/checksums, acquisitions, source and output grids,
licenses, attributions, retrieval times and manual findings.

## Publish checked-in data

Use the hosted development database in the ignored `.env` file:

```sh
uv sync --locked
uv run --locked --env-file .env floodbeacon publish-imagery
```

Alternatively:

```sh
uv run --locked --env-file .env python scripts/prepare_bridge_imagery.py --publish-only
```

Publishing checked-in files needs only the default API dependencies. It neither
retrieves satellite imagery nor imports geospatial libraries. The schema is
initialized explicitly by this command, outside GET requests.

## Rebuild on the processing machine

The existing research windows and manifests are ignored under
`data/research/bridge-demo-other/` and `data/research/bridge-demo-nepal/`.
Their acquisition scripts are `scripts/prepare_bridge_demo_derna.py` and
`scripts/prepare_bridge_demo_nepal.py`; those original research scripts use the
`damage-research` group. Run them only when rebuilding missing inputs. Rech
source retrieval and date-folder verification remain in
`scripts/prepare_rech_satellite.py`, documented in `docs/rech-satellite.md`.

```sh
uv run --locked --group processing python scripts/prepare_bridge_imagery.py
# To rebuild and publish together:
uv run --locked --group processing --env-file .env python scripts/prepare_bridge_imagery.py --publish
```

The reusable code is `src/floodbeacon/imagery.py`. It verifies source TIFF hashes,
warps the Derna and Nepal RGB windows to EPSG:3857 with bilinear resampling,
resamples source validity masks with nearest neighbour, and exports RGBA PNGs.
No color enhancement is applied. The approved Rech PNGs are reused unchanged.
PNG width/height and four WGS84 image-source corners describe the exported grid.
This is a bounded image overlay; it does not require a world tile pyramid or a
map tile account. Small comparison indices use the same imagery, nearest-neighbour
crop zooms and a yellow attention box.

Review squares are 90 metres in an appropriate UTM CRS (Rech EPSG:25832,
Derna EPSG:32634, Nepal EPSG:32645), exported as closed WGS84 polygons. They are
attention annotations, not surveyed damage boundaries. Observations on one date
combine all available local patches. Missing patches do not imply intact bridges.

## Coverage and findings

| Case | Available observations | Findings and limitations |
| --- | --- | --- |
| Germany, Rech | 2021-02-11; 2021-07-18 | Complete crossing before; remnant and missing span after. Copernicus `Destroyed` is a separate agency assessment. Exact image UTC and failure time remain unknown. |
| Libya, Derna | 2023-07-01; 2023-09-13 | Two Wadi crossings visible before and absent after. UNOSAT preliminary area assessment is separate; exact inventory identities were not independently matched. |
| Nepal, Syabrubesi | 2023-09-17; 2026-05-27; 2026-08-27 | Two crossing comparisons have an old baseline. May 2026 contains only a 3 m road reference, marked uncertain; it cannot assess the narrow footbridge. Intervening 2025 damage is not ruled out for the footbridge. |

All findings use `assessment_method: manual image review`. No model accuracy,
exact destruction time or surrounding route passability is claimed. The exported
source validity masks do not encode a complete cloud, shadow or reliability mask.
Source publication timestamps are retained as supplied; unspecified timezone or
availability times are not invented.

Rech derivatives are CC BY-SA 4.0; regional Germany imagery is CC BY-NC 4.0; Derna and Nepal imagery is CC BY-NC 4.0,
with Maxar, Vantor and Planet attribution recorded per image. These latter assets
are for the noncommercial research/demo use described here. Raw TIFFs remain
ignored. All curated images, comparisons and metadata together are approximately
34 MiB including the regional tile pyramid; detail map images alone total approximately 19 MiB. Rech's two map images
are approximately 1.31 MiB.

## Verification

`tests/test_imagery_catalog.py` checks committed image checksums and PNG dimensions,
case/date coverage, provenance fields, unknown acquisition times, the road-only
May reference, rejection of altered immutable content, and publication idempotency
with mocked database writes. It does not estimate detector performance.

```sh
uv run --locked pytest -q tests/test_imagery_catalog.py
```
