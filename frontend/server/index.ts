import http from 'node:http';
import { createPool, loadState, saveChanges } from './db';
import { isValidActor, parseAction, runAction } from '../src/logic/actions';

// Small API between the browser and PostgreSQL.
//   GET  /api/state    → the whole dispatch state
//   POST /api/actions  → { actor, action }: run one change through the shared rules, save it
//   GET  /api/stream   → Server-Sent Events: "changed" after every saved change
// Logs name action types, ids and actors only — never health details (CLAUDE.md rule 7).

const PORT = Number(process.env.PORT ?? 8787);
const MAX_BODY_BYTES = 64 * 1024;
/** One lock id for all writes, so two dispatchers never overwrite each other's change. */
const WRITE_LOCK = 4_271_001;

const pool = createPool();
const listeners = new Set<http.ServerResponse>();

function send(res: http.ServerResponse, status: number, body: unknown) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
  res.end(JSON.stringify(body));
}

function readBody(req: http.IncomingMessage): Promise<unknown> {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks: Buffer[] = [];
    req.on('data', (c: Buffer) => {
      size += c.length;
      if (size > MAX_BODY_BYTES) {
        reject(new Error('body too large'));
        req.destroy();
      } else chunks.push(c);
    });
    req.on('end', () => {
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString('utf8')));
      } catch {
        reject(new Error('invalid JSON'));
      }
    });
    req.on('error', reject);
  });
}

/** Safe to log: no row contents (pg's `detail` can include whole rows). */
function describeError(err: unknown): string {
  const e = err as { code?: string; message?: string };
  return `${e.code ?? 'error'} ${e.message ?? ''}`.trim();
}

function broadcast() {
  for (const res of listeners) res.write(`event: changed\ndata: ${Date.now()}\n\n`);
}

async function handleAction(req: http.IncomingMessage, res: http.ServerResponse) {
  let body: unknown;
  try {
    body = await readBody(req);
  } catch (err) {
    return send(res, 400, { ok: false, reasons: [(err as Error).message] });
  }
  const { actor, action: raw } = (body ?? {}) as { actor?: unknown; action?: unknown };
  const action = parseAction(raw);
  if (!action) return send(res, 400, { ok: false, reasons: ['Unknown or malformed action.'] });
  if (!isValidActor(actor)) return send(res, 400, { ok: false, reasons: ['Unknown actor.'] });

  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query('SELECT pg_advisory_xact_lock($1)', [WRITE_LOCK]);
    const before = await loadState(client);
    const result = runAction(before, action, { now: new Date(), actor });
    if (!result.ok) {
      await client.query('ROLLBACK');
      console.log(`refused ${action.type} by ${actor}`);
      return send(res, 422, result);
    }
    await saveChanges(client, before, result.state);
    await client.query('COMMIT');
    console.log(`saved ${action.type} by ${actor}: ${result.events.length} event(s)`);
    broadcast();
    return send(res, 200, { ok: true, state: result.state });
  } catch (err) {
    await client.query('ROLLBACK').catch(() => {});
    console.error(`failed ${action.type} by ${actor}: ${describeError(err)}`);
    return send(res, 500, { ok: false, reasons: ['The database could not save this change. Try again.'] });
  } finally {
    client.release();
  }
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url ?? '/', 'http://localhost');
  try {
    // Production API relay: forward the operator's bearer token; never inject a public key.
    if (/^\/intake\/(incidents(?:\/[a-zA-Z0-9-]+)?|reports\/gemini)$/.test(url.pathname)
        && (req.method === 'GET' || req.method === 'PATCH')) {
      if (!req.headers.authorization?.startsWith('Bearer ')) {
        return send(res, 401, { detail: 'Operator authentication required' });
      }
      const upstream = new URL(url.pathname.replace(/^\/intake/, '') + url.search,
        process.env.INTAKE_API_URL || 'http://127.0.0.1:8000');
      const body = req.method === 'PATCH' ? JSON.stringify(await readBody(req)) : undefined;
      try {
        const response = await fetch(upstream, { method: req.method, body,
          headers: { Authorization: req.headers.authorization, 'Content-Type': 'application/json' },
          signal: AbortSignal.timeout(12000), redirect: 'error' });
        return send(res, response.status, await response.json());
      } catch {
        return send(res, 502, { detail: 'Intake API unavailable' });
      }
    }
    if (req.method === 'GET' && url.pathname === '/api/state') {
      return send(res, 200, await loadState(pool));
    }
    if (req.method === 'POST' && url.pathname === '/api/actions') {
      return await handleAction(req, res);
    }
    if (req.method === 'GET' && url.pathname === '/api/stream') {
      res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-store', Connection: 'keep-alive' });
      res.write(': connected\n\n');
      listeners.add(res);
      req.on('close', () => listeners.delete(res));
      return;
    }
    if (req.method === 'GET' && url.pathname === '/api/health') {
      await pool.query('SELECT 1');
      return send(res, 200, { ok: true });
    }
    return send(res, 404, { ok: false, reasons: ['Not found.'] });
  } catch (err) {
    console.error(`${req.method} ${url.pathname}: ${describeError(err)}`);
    return send(res, 500, { ok: false, reasons: ['Server error.'] });
  }
});

// Keep proxies and browsers from closing idle event streams.
setInterval(() => {
  for (const res of listeners) res.write(': ping\n\n');
}, 25_000).unref();

server.listen(PORT, () => {
  console.log(`FloodBeacon API on http://localhost:${PORT} (database: ${process.env.DATABASE_URL ? 'DATABASE_URL' : 'local floodbeacon'})`);
});
