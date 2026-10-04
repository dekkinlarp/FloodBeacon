# Satellite imagery integration

The Routes tab in `floodbeacon-dashboard` reads the Germany bridge imagery
catalog from FastAPI. It compares the February 11 and July 18, 2021 satellite
observations at Nepomukbrücke in Rech. The backend also publishes the Derna,
Libya and Syabrubesi, Nepal catalogs. The frontend currently selects Germany.

## Run the two applications

Backend, from this repository:

```sh
uv sync --locked
# Set DATABASE_URL in .env to the shared development connection.
uv run --locked --env-file .env uvicorn floodbeacon.api:app --reload --port 8000
```

Frontend, from the sibling `floodbeacon-dashboard` repository:

```sh
# Dependencies are already installed on the processing machine.
# On a fresh clone, run npm install first.
cp .env.example .env.local
npm run dev
```

`VITE_FLOODBEACON_API_URL` defaults to `http://localhost:8000`. Open
`http://localhost:5173` and select **Routes**. This view uses the API; the other
dashboard tabs retain their existing prototype data. CORS permits any origin
for the hackathon. `DATABASE_URL` is required and is never sent to the frontend.

## Map delivery

The checked-in PNGs are served under `/static/imagery/`. Each image has four
WGS84 corners in NW, NE, SE, SW order and is prepared on a Web Mercator grid.
MapLibre renders these as image sources with raster layers. A date change
replaces the image sources and bridge findings without resetting the camera.
The current bounded bridge patches do not need an XYZ tile server or S3.

Image bytes are not stored in PostgreSQL. PostgreSQL holds case metadata,
immutable run metadata, dated observations and bridge GeoJSON. Static assets
are included in the Python package, so an API checkout or installed wheel can
serve them without downloaded research TIFFs or geospatial dependencies.

## API contract

| Case | Identifier | Observations |
| --- | --- | --- |
| Germany, Rech | `ahr-2021` | 2021-02-11 and 2021-07-18 |
| Libya, Derna | `derna-2023` | 2023-07-01 and 2023-09-13 |
| Nepal, Syabrubesi | `nepal-2026` | 2023-09-17, 2026-05-27 road reference, 2026-08-27 |

`GET /cases/{case_id}/imagery` returns:

- `case_id`, `name`, `country`, WGS84 `bounds`, `run_id`, and `generated_at`.
- `observations`: acquisition date/time, label, georeferenced image URLs,
  dimensions, checksums, attribution, license, provenance and dated bridge
  GeoJSON.
- `bridges`: bridge location, comparison URLs, separate agency evidence,
  unknown failure time and limitations.

`GET /cases/{case_id}/imagery/{observation_id}/bridges` returns that observation's
annotations. Both endpoints accept `?run_id=...` to select an immutable
publication. The default selects the latest **imagery** run, even if a different
analysis was published more recently. `/docs` provides the typed response
schemas. Missing cases, runs or observations return 404; unavailable database
storage returns a sanitized 503.

Square polygons locate manually reviewed crossings. Findings describe visible
continuity or missing spans on the acquisition date. They do not establish an
exact failure time, a surveyed damage boundary or surrounding road passability.
Missing observations remain unknown. Nepal's May reference is a coarse 3 m
road image and does not cover both reviewed crossings.

## Precompute and publish

The project owner runs preparation once on the processing machine:

```sh
uv run --locked --group processing python scripts/prepare_bridge_imagery.py
uv run --locked --env-file .env floodbeacon publish-imagery
```

Preparation uses the previously retrieved research manifests and TIFF windows;
see the retrieval commands in [bridge research](bridge-demo-research.md).
Rech's curated PNGs are retained unchanged. Derna and Nepal windows are warped
to Web Mercator with their validity masks and packaged alongside compact
comparisons. A bundled catalog records dates, provenance, source/output
checksums, licenses and manual findings.

`publish-imagery` needs only the normal API environment and the checked-in
catalog. It verifies catalog and asset hashes, initializes the schema if needed,
and publishes each complete case in one database transaction. The run ID is
derived from the catalog contents; publishing the same contents again reports
`unchanged`. It never fetches imagery, runs a model or stores image bytes.

Catalog: `src/floodbeacon/static/imagery/bridge-catalog/catalog.json`.
Keep this file and its matching image files in the same Git revision. Germany
imagery is CC BY-SA 4.0; Libya and Nepal imagery is CC BY-NC 4.0. Preserve each
image's attribution and license when displaying or redistributing it.

## Shared development database checks

All current publication, serving and real database verification use the hosted
development database. The local Compose PostgreSQL container is stopped.
To run the isolated transaction tests against that instance without exposing
the URL in shell output:

```sh
uv run --locked --env-file .env python -c 'import os, pytest; os.environ["FLOODBEACON_TEST_DATABASE_URL"] = os.environ["DATABASE_URL"]; raise SystemExit(pytest.main(["tests/test_api.py", "tests/test_db.py", "tests/test_imagery_api.py"]))'
```

These tests create unique synthetic case IDs and clean up only their own cases.
They do not delete or replace the curated imagery publications.

## Delivery verification, October 4, 2026

All three real catalogs were published to the hosted development instance.
Live HTTP checks returned every catalog, dated bridge annotation and image file
with the expected byte counts and permissive CORS. Repeated publication reported
`unchanged` for all three cases. The full Python suite passed 82 tests, including
the isolated PostgreSQL transaction tests on that same hosted instance.

A fresh `uv sync --locked` environment served database health, all catalogs and
all image files and repeated publication successfully, without Rasterio, NumPy,
Pillow or Torch installed. The built wheel includes all 16 curated image assets
referenced by the catalog and contains no raw TIFFs or `.env` file.

The frontend build and lint passed; lint retains three existing warnings in the
prototype code. Browser checks covered the real Germany observations, date
changes with the camera preserved, map panning, bridge-square clicks, desktop
and narrow layouts, and the light theme. A shared navigation font shorthand
warning was reproduced and fixed; subsequent navigation and theme changes
produced no new console errors or warnings. These checks validate delivery and
interaction, not automated damage detection accuracy.
