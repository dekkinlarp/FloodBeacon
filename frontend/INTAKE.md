# Live Twilio / Gemini integration

The default dashboard now reads the Python intake service. Its existing synthetic dispatcher is
available only at `?demo=1` (or the **Synthetic demo** link). Real SMS reports are never mixed with
fake teams, travel times, medical assessments, or invented coordinates.

## Start all services

From `FloodBeacon/twillio` in two terminals:

```sh
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```sh
source .venv/bin/activate
python -m app.worker
```

Keep your ngrok tunnel and Twilio webhook configuration for incoming SMS as described in
`../twillio/README.md`. Ngrok continues to point to **8000**, not the frontend port.

From `FloodBeacon/frontend`, using **Node 22.12+** (Node 22.13 was used for testing):

```sh
npm install
npm run dev
```

Open the local Vite URL (normally `http://localhost:5173`). Enter the `OPERATOR_API_KEY` from
`../twillio/.env` in the connection form. Do not enter your Gemini key or Twilio token there.
The operator key remains in browser memory only and is cleared on disconnect or page reload.
Never set it in a `VITE_*` environment variable: those values are bundled into browser code.

No PostgreSQL server is required for the live intake screen. The original synthetic dispatcher
and its PostgreSQL API remain available separately; see the original README for that workflow.

## Data flow

SMS → Twilio webhook → SQLite → Gemini worker → `/incidents` → same-origin `/intake` proxy → feed.

- Polling runs every five seconds after the preceding request completes.
- One feed row corresponds to one canonical backend case, not each extraction version. Follow-up
  texts update that row; multiple reported situations remain separate within its detail panel.
- Detail view shows the summary, people count, address/house number/postal code, hazards,
  assistance needs, quoted evidence, and original messages from `/incidents/{id}`.
- Unknown counts remain unknown. Missing coordinates keep a case visible as **Unlocated**.
- Only valid operator-supplied coordinates for single-location cases become map pins.
- Backend `PATCH /incidents/{id}` saves **Mark verified**, **Assessing**, and **Mark resolved**
  actions with an operator-entered reason and optimistic version checking. These do not dispatch
  a team or send an SMS. Assignment/team management continues to be demo-only.
- Connection failures show an error and retain the last fetched reports as potentially stale.
  They never load synthetic data as a fallback.
- Empty feed means no extracted cases yet. Pending or failed messages are still inspectable via
  the backend `/reports` and `/reports/gemini` APIs; they are not silently promoted into incidents.

## Proxy configuration

Vite dev and preview proxy `/intake/*` to `http://127.0.0.1:8000` by default. To change the
backend, copy `.env.example` to `.env.local` and set `INTAKE_API_URL`. Restart Vite after changes.
This environment variable is server-side; no credentials are stored there.

For an actual deployment, serve the dashboard over HTTPS and route `/intake` to the Python
API with that prefix stripped. The existing Node API server also supports a bearer-token
forwarding relay for intake GET/PATCH routes. The bearer token is required by Python on every
request. Never publish `.env`, database files, or private reports. The frontend does not provide
organizational accounts or role management beyond the backend's existing operator key.

The basemap uses OpenFreeMap and displays attribution. If tiles/WebGL fail, the feed and detail
panel still work. No geocoding service or SMS data is sent to the basemap provider.

## Verify

```sh
npm test
npm run build
```

For end-to-end testing: connect the dashboard, send a synthetic SMS, wait for the worker to log
`Gemini report saved`, and observe a new case. Answer the house-number follow-up and confirm the
same case updates within the next refresh. Inspect original messages and evidence. If testing an
operator action, enter a reason and verify the change persists after refreshing the page.

The repository is cloned inside `frontend/` with its own `.git` directory. It remains a separate
Git checkout; decide whether to vendor it or add a proper submodule before committing the parent
repository. No repositories were pushed by this integration.

The live map shares the original dispatcher’s OpenFreeMap dark style, 50° pitch and −17°
bearing, 2D/2.5D toggle, and building extrusion layer. Buildings become visible from zoom 13
and grow to mapped heights by zoom 14, where height data exists. This is an OSM-derived vector
basemap, not satellite imagery or a flood-depth model. The live view initially centers on Sumas
Prairie and fits known report coordinates; unlocated reports never acquire placeholder pins.


## Ahr Valley satellite integration

The live intake map now includes a historical satellite selector for Ahr Valley,
Derna and Nepal, with dated imagery, manual bridge review squares, comparison
links and a separate post-event Copernicus overlay for Germany. Select Germany
and a date; use the bridge button for detailed pixels or Rescue reports to
return to the intake pins. Date changes preserve the camera. Off removes the
satellite layers. The initial map center is Rech in the Ahr Valley, Germany.

The curated catalog and imagery from ../satellite/src/floodbeacon/static/imagery
are copied to public/static/imagery and included in Vite builds. This is a bundled
repository snapshot, not a live PostgreSQL feed; no satellite API or credentials
are required. To update it after fetching satellite, copy that entire imagery
directory again, keeping the catalog and assets together. Source provenance and
licenses are retained, including CC BY-SA and CC BY-NC attributions.
Historical imagery does not represent current conditions. The synthetic Ahr
rescue records are fictional exercises, not July 2021 rescue evidence.
