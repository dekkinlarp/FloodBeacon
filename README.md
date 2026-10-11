# FloodBeacon

Flood disaster assessment prototype combining SMS help reports, Gemini extraction, and an
operator dashboard. This monorepo contains the intake backend, dispatcher frontend, and satellite analysis service.

- [`twillio/`](twillio/README.md): Python FastAPI webhook, Gemini worker, conversation storage,
  address follow-ups, authenticated incident/report APIs.
- [`frontend/`](frontend/README.md): React dispatcher cloned from
  [Flood-Beacon_Dispatch](https://github.com/dekkinlarp/Flood-Beacon_Dispatch), running as a
  static synthetic dispatcher demo with bundled historical satellite imagery.

- [`satellite/`](satellite/README.md): Satellite analysis, curated bridge imagery, and the map REST API.

## Run the frontend demo

In `frontend/`, use the Node version in `.nvmrc`, then:

```bash
pnpm install --frozen-lockfile
pnpm run dev
```

The default screen combines synthetic dispatch/team interactions with bundled historical
satellite imagery. No backend or credentials are required. Changes stay in browser memory
and reset on refresh. The street basemap requires internet access.

See [frontend setup](frontend/README.md) and [Cloudflare automatic deployment](frontend/DEPLOYMENT.md).
The Twilio and satellite services remain available for separate backend development.

## Repository layout

All three components are tracked by this root Git repository. Run Git commands from the
repository root; `frontend/` and `satellite/` are ordinary directories, not nested checkouts
or submodules. Their original commit histories are retained as parents of the consolidation
commit and on the `consolidation/frontend-history` and `consolidation/satellite-history` branches.
Existing component setup commands and paths are unchanged. Follow `satellite/AGENTS.md` when
working on the satellite service. Local credentials, virtual environments, downloaded inputs,
and generated artifacts remain ignored.
