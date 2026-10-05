# FloodBeacon

Flood disaster assessment prototype combining SMS help reports, Gemini extraction, and an
operator dashboard. Satellite flood analysis remains a separate integration effort.

- [`twillio/`](twillio/README.md): Python FastAPI webhook, Gemini worker, conversation storage,
  address follow-ups, authenticated incident/report APIs.
- [`frontend/`](frontend/INTAKE.md): React dispatcher cloned from
  [Flood-Beacon_Dispatch](https://github.com/dekkinlarp/Flood-Beacon_Dispatch), connected to the
  live intake feed by default. Synthetic dispatcher demo is explicitly available at `?demo=1`.

## Run locally

1. Configure `twillio/.env` using `twillio/.env.example`.
2. In `twillio/`, activate `.venv` and run `uvicorn app.main:app --port 8000`.
3. In another terminal with the same environment, run `python -m app.worker`.
4. In `frontend/`, use Node 22.12+ (`nvm use` reads `.nvmrc`), run `npm ci`, then `npm run dev`.
5. Open the Vite URL, normally `http://localhost:5173`, and enter `OPERATOR_API_KEY` from
   `twillio/.env` in the connection form. Do not use your Gemini key or Twilio auth token.
6. Keep ngrok forwarding to port **8000** and configure the Twilio POST webhook as
   `<public-tunnel>/webhooks/twilio/inbound`. Send a synthetic SMS to verify the flow.

The dashboard polls every five seconds. It uses canonical cases so follow-up messages update
existing rows. The detail panel shows Gemini summaries, structured address fields, evidence,
and source messages. Human review/status updates persist through the Python API. Reports without
coordinates remain visible in the queue. Live mode does not use fake teams or dispatch assignments.

See [frontend integration setup](frontend/INTAKE.md) and [backend setup](twillio/README.md) for
configuration, endpoints, test commands and limitations. The live dashboard needs no PostgreSQL.

The cloned frontend retains its own Git checkout. No submodule registration, parent commit, or
remote push is performed automatically. Decide how to include it before committing the parent.
