import type { DispatchState } from '../logic/dispatch';
import type { ActionBody } from '../logic/actions';
import { validateDataset } from '../logic/validateData';

// Talks to the API server (server/index.ts), which owns the PostgreSQL database.
// In development Vite forwards /api to it (vite.config.ts).

export type ActionResponse = { ok: true; state: DispatchState } | { ok: false; reasons: string[] };

/** Loads the whole state. Throws if the server is unreachable or sends data that fails validation. */
export async function fetchState(signal?: AbortSignal): Promise<DispatchState> {
  const res = await fetch('/api/state', { signal, headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(`Server answered ${res.status}`);
  const state = (await res.json()) as DispatchState;
  const errors = validateDataset({ incidents: state.incidents, health: state.health, teams: state.teams });
  // Messages name ids and fields only, never health values.
  if (errors.length > 0) throw new Error(`Server data is invalid:\n${errors.join('\n')}`);
  return state;
}

export async function postAction(actor: string, action: ActionBody): Promise<ActionResponse> {
  try {
    const res = await fetch('/api/actions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actor, action }),
    });
    const body = (await res.json()) as ActionResponse;
    if (body && typeof body === 'object' && 'ok' in body) return body;
    return { ok: false, reasons: [`Server answered ${res.status}.`] };
  } catch {
    return { ok: false, reasons: ['Could not reach the server. The change was not saved.'] };
  }
}

/** Calls `onChange` whenever the server saves a change. Returns an unsubscribe function. */
export function subscribeToChanges(onChange: () => void, onDown: () => void): () => void {
  const source = new EventSource('/api/stream');
  source.addEventListener('changed', onChange);
  source.onerror = onDown;
  return () => source.close();
}
