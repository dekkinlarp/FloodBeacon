# FloodBeacon

Historical satellite flood analysis, agency infrastructure-damage evidence,
and access-risk scenarios for a future first-responder map frontend. Python/uv
batch analysis publishes complete PostgreSQL runs; FastAPI and an HTML preview
read those same artifacts.

The two cases are the July 2021 Ahr Valley flood in Germany (CEMS EMSR517 AOI15)
and the November 2021 Merritt/Nicola Valley floods in British Columbia.

## What the POC does

- A supervised Random Forest classifies surface water from pre/post Sentinel-1
  imagery and maps candidate newly water-like areas and asset exposure.
- Ahr transport destruction/damage grades come from **Copernicus agency
  assessments**, separately from model results. BC currently has bridge/culvert
  inventory context and historical gauge/rainfall observations; its historical
  impact PDF has not been converted into damage labels.
- Hypothetical 50/100 m footprint expansions illustrate sensitivity. They have
  **no forecast time or likelihood**. No model predicts that a bridge will
  collapse in two days, and no layer certifies road passability or boat access.

Automated structural damage is a separate next product decision. The deeper
[damage research and CUDA experiments](docs/damage-identification-research.md)
test public pretrained models and distinguish building damage, road disruption
and bridge destruction. Research outputs are separate from the API. The local
RTX 3080 Laptop GPU now works with Python 3.14 and PyTorch CUDA; the current
production flood classifier remains a CPU Random Forest.

## Run locally

Requires uv and Docker Compose. [Python's release list](https://www.python.org/downloads/)
was checked on 2026-10-03: Python 3.14.8 is the current stable release and is
pinned in `.python-version`. Dependencies are locked in `uv.lock`.
[PostgreSQL 18.6](https://www.postgresql.org/docs/release/) is pinned in Compose.

```sh
uv python install 3.14.8
uv sync --locked
docker compose up -d --wait
uv run floodbeacon init-db
uv run floodbeacon train --chips-per-event 3
```

If the installed uv does not yet list Python 3.14.8, use Astral's current official
interpreter metadata. This was the successful fallback for uv 0.11.16 here:

```sh
uv python install --python-downloads-json-url https://raw.githubusercontent.com/astral-sh/uv/main/crates/uv-python/download-metadata.json 3.14.8
```

Training prints the locally generated `model` path. Pass that exact path to
batch processing; the following path is from the initial verified training run:

```sh
uv run floodbeacon batch --case all --model data/models/water-rf-10958a17b65a7d7f/model.pkl
uv run floodbeacon preview --output-dir artifacts
uv run uvicorn floodbeacon.api:app --host 127.0.0.1 --port 8000
```

Open `artifacts/index.html` for a case selector, evidence layers, observations,
source details and limitations. Its basemap and JavaScript/CSS dependencies
require internet. The API documentation is at
[localhost:8000/docs](http://localhost:8000/docs).
`--case ahr-2021` or `--case bc-2021` runs one case. Inputs, locally trained
models and previews live in ignored `data/` and `artifacts/` directories.

PostgreSQL binds to `127.0.0.1:55432` and persists under `/var/lib/postgresql`
using the PostgreSQL 18 layout. Default local credentials are in `.env.example`.
The application reads the `DATABASE_URL` environment variable; it does not
automatically load `.env`. Export an override when changing credentials or port.
`docker compose stop` preserves data for later use.

## REST API

GET requests read completed runs; they do not download imagery or train models.
Use a returned `run_id` to keep frontend requests on the same immutable run.

| Resource | Endpoint |
| --- | --- |
| Database health | `/health` |
| Cases | `/cases` |
| Completed runs | `/cases/{case_id}/runs` |
| Run provenance and parameters | `/cases/{case_id}/runs/{run_id}` |
| GeoJSON | `/cases/{case_id}/layers/{layer}?run_id=...` |
| Historical observations | `/cases/{case_id}/observations?run_id=...` |

Layer names include `assets`, `reported_damage`, `agency_flood_reference`,
`modeled_new_water`, `modeled_event_water`, `exposure`, `valid_coverage`,
`unknown_coverage`, `scenario_50m`, and `scenario_100m`; available names are in
each run's metadata. Empty layers indicate no records in that layer, not proof
of no damage. GeoJSON uses WGS84 longitude/latitude. Layer responses support
`limit`, `offset`, and `bbox=west,south,east,north`; bbox filtering uses geometry
**envelope overlap**, without clipping or exact intersection.

```sh
curl http://127.0.0.1:8000/cases
curl 'http://127.0.0.1:8000/cases/ahr-2021/layers/reported_damage?limit=20'
curl http://127.0.0.1:8000/cases/bc-2021/observations
uv run pytest
```

## Evidence and verification

The initial real Sen1Floods11 training sampled nine training chips and three
Bolivia event-holdout chips. Pooled water IoU was 0.8418, but one holdout chip
had F1 0.1034; see [the full model report](docs/model.md). Those metrics do not
validate Ahr/BC transfer. The six ML contract/grid tests passed. Public source
queries and actual satellite TIFF-header reads succeeded without accounts.
Source ingestion also identified 4,323 Ahr transportation features, including
762 positive damage grades and 53 destroyed grades, plus 77 agency flood
reference features; BC's current inventory query returned ten structures.

Both real case batches published PostgreSQL runs and the live API returned
their data; both HTML case maps, the selector, and BC observation plots were
checked in the browser. Final verification passed **41 tests**, including real
PostgreSQL transactions, followed by compilation and live API checks. A current
Starlette/httpx TestClient deprecation warning remains; it did not fail tests.

To serve the preview locally:

```sh
uv run python -m http.server 8080 --bind 127.0.0.1 --directory artifacts
```

Open [the inspection map](http://127.0.0.1:8080/). Its candidate-exposure overlay
shows flagged intersections; the API exposure layer retains every asset and its
unknown/not-detected status.

To inspect research imagery with synchronized zoom, human labels and separate
model predictions, run `uv run --group damage-research python scripts/render_dataset_viewer.py`
after retrieving the Ahr/BRIGHT research inputs. Open the
[raw-data viewer](http://127.0.0.1:8080/dataset-viewer/).
The [SpaceNet 8 experiment](docs/spacenet8-experiment.md) has its own raw-photo,
annotation and prediction gallery; these are research outputs.

The Ahr model output had **poor agreement** with the retrospective agency
reference: modeled new-water area 0.8028 km², reference union 4.806 km²,
intersection 0.3601 km², overlap IoU 0.0686. The reference combines flood trace
and flooded-area evidence from July 18, while SAR was acquired July 15; this is
a dated spatial comparison, **not detector accuracy**. Terrain shadow/layover
has not been fully screened. Treat local output as experimental. Ahr yielded
125 candidate exposed transportation features; BC yielded zero candidates among
ten current inventory structures. Zero candidates does not establish intact
bridges or passable routes. BC has no ingested compatible flood reference for
local evaluation. See each run's metadata and preview limitations.

Sen1Floods11's official label catalog declares `proprietary` and the authors'
repository has an unresolved missing-license issue. Training-data/model rights
are recorded as unresolved; keep downloaded inputs and trained artifacts local
for this research POC. Source access currently needs no account for the tested
baseline, but access terms and quotas are separate from redistribution rights.

- [Engineering agreement](AGENTS.md)
- [Research, sources and implementation status](docs/research.md)
- [Current model and reproducibility](docs/model.md)
- [Pretrained structural-damage model research](docs/pretrained-models.md)
- [Bridge inventories and structural-data gaps](docs/structural-data.md)
