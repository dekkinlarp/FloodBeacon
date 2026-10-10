import { createContext, useContext, useEffect, useMemo, useReducer, useRef, useState, type ReactNode } from 'react';
import type { IncidentStatus, TeamStatus } from '../types';
import type { DispatchResult, DispatchState } from '../logic/dispatch';
import type { FeedbackInput } from '../logic/feedback';
import type { ActionBody } from '../logic/actions';
import { runAction } from '../logic/actions';
import { fetchState, postAction, subscribeToChanges } from '../data/api';
import type { DemoLogEntry, DemoScript } from '../logic/demo';
import { runDueSteps } from '../logic/demo';

/** Placeholder until login exists (Person 3; PLAN.md Q6). */
export const CURRENT_ACTOR = 'dispatcher';

/** Actor name for changes made from a team's own view. */
export const teamActor = (teamId: string) => `team:${teamId}`;

type Action = { at: Date; actor: string } & ActionBody;

type Control =
  | { type: 'clearError' }
  | { type: 'reset'; data: DispatchState }
  /** New data from the server; keeps demo progress and the current error. */
  | { type: 'replace'; data: DispatchState }
  | { type: 'setError'; reasons: string[] }
  | { type: 'demoTick'; script: DemoScript; simStart: number; now: number };

interface StoreState {
  data: DispatchState;
  /** Reasons the last action was refused, if it was. */
  error: string[] | null;
  /** Demo script steps already run (applied or skipped), and what happened. */
  demoDone: string[];
  demoLog: DemoLogEntry[];
}

function run(data: DispatchState, action: Action): DispatchResult {
  const { at, actor, ...body } = action;
  return runAction(data, body as ActionBody, { now: at, actor });
}

function fresh(data: DispatchState): StoreState {
  return { data, error: null, demoDone: [], demoLog: [] };
}

function reducer(store: StoreState, action: Action | Control): StoreState {
  if (action.type === 'clearError') return { ...store, error: null };
  if (action.type === 'reset') return fresh(action.data);
  if (action.type === 'replace') return { ...store, data: action.data };
  if (action.type === 'setError') return { ...store, error: action.reasons };
  if (action.type === 'demoTick') {
    // Runs on the latest state, so scripted steps and manual actions never race.
    const r = runDueSteps(store.data, action.script, new Set(store.demoDone), action.simStart, action.now);
    if (r.log.length === 0) return store;
    return {
      ...store,
      data: r.state,
      demoDone: [...store.demoDone, ...r.log.map((e) => e.stepId)],
      demoLog: [...store.demoLog, ...r.log],
    };
  }
  const result = run(store.data, action);
  return result.ok ? { ...store, data: result.state, error: null } : { ...store, error: result.reasons };
}

interface StoreApi {
  data: DispatchState;
  error: string[] | null;
  demoLog: DemoLogEntry[];
  demoDone: ReadonlySet<string>;
  assign: (incidentId: string, teamId: string, backup: boolean) => void;
  setIncidentStatus: (incidentId: string, to: IncidentStatus) => void;
  setTeamStatus: (teamId: string, to: TeamStatus) => void;
  recall: (teamId: string) => void;
  confirmHealth: (incidentId: string) => void;
  /** `actor` defaults to the dispatcher (e.g. a check-in received by radio). */
  checkIn: (teamId: string, actor?: string) => void;
  /** From the team view; the team is the actor. */
  fieldReport: (teamId: string, to: IncidentStatus) => void;
  submitFeedback: (input: FeedbackInput) => Promise<DispatchResult>;
  /** Where live data comes from: the database server, or fake data when it is unreachable. */
  source: DataSource;
  acknowledgeAlert: (alertId: string) => void;
  clearError: () => void;
  /** Replace everything (new data, empty demo progress). */
  reset: (data: DispatchState) => void;
  /** Run demo script steps that are due at simulated time `now`. */
  demoTick: (script: DemoScript, simStart: number, now: number) => void;
}

export type DataSource = 'connecting' | 'database' | 'fake';

const StoreContext = createContext<StoreApi | null>(null);

/**
 * Dispatch state for the app. In live mode it comes from the API server
 * (PostgreSQL): every change is sent there, run through the same rules, saved,
 * and pushed to every open screen. In demo mode, or when the server cannot be
 * reached, changes run locally in memory on fake data.
 * `getNow` is the app clock (simulated in demo mode); local actions are stamped with it.
 */
export function DispatchStoreProvider({
  initial,
  getNow,
  live,
  children,
}: {
  initial: DispatchState;
  getNow: () => Date;
  /** False during the demo: the demo always runs locally. */
  live: boolean;
  children: ReactNode;
}) {
  const [store, send] = useReducer(reducer, initial, fresh);
  const [source, setSource] = useState<DataSource>('connecting');
  const liveRef = useRef(live);
  liveRef.current = live;

  // Load from the server whenever live mode starts, and follow its changes.
  useEffect(() => {
    if (!live) return;
    const abort = new AbortController();
    const load = () =>
      fetchState(abort.signal)
        .then((data) => {
          if (!liveRef.current) return; // the demo started meanwhile; keep its data
          send({ type: 'replace', data });
          setSource('database');
        })
        .catch((err: unknown) => {
          if ((err as Error).name === 'AbortError' || !liveRef.current) return;
          setSource('fake');
        });
    load();
    const unsubscribe = subscribeToChanges(load, () => {});
    return () => {
      abort.abort();
      unsubscribe();
    };
  }, [live]);

  const remote = live && source === 'database';

  const api = useMemo<StoreApi>(() => {
    const at = getNow;
    /** Runs a change on the server (live) or locally (demo / fake data). */
    const act = async (actor: string, body: ActionBody): Promise<DispatchResult> => {
      if (!remote) {
        const action = { ...body, at: at(), actor } as Action;
        const result = run(store.data, action);
        send(action);
        return result;
      }
      const r = await postAction(actor, body);
      if (r.ok) {
        send({ type: 'replace', data: r.state });
        send({ type: 'clearError' });
        return { ok: true, state: r.state, events: [] };
      }
      send({ type: 'setError', reasons: r.reasons });
      return r;
    };
    const fire = (actor: string, body: ActionBody) => void act(actor, body);
    return {
      data: store.data,
      error: store.error,
      demoLog: store.demoLog,
      demoDone: new Set(store.demoDone),
      source,
      assign: (incidentId, teamId, backup) => fire(CURRENT_ACTOR, { type: 'assign', incidentId, teamId, backup }),
      setIncidentStatus: (incidentId, to) => fire(CURRENT_ACTOR, { type: 'incidentStatus', incidentId, to }),
      setTeamStatus: (teamId, to) => fire(CURRENT_ACTOR, { type: 'teamStatus', teamId, to }),
      recall: (teamId) => fire(CURRENT_ACTOR, { type: 'recall', teamId }),
      confirmHealth: (incidentId) => fire(CURRENT_ACTOR, { type: 'confirmHealth', incidentId }),
      checkIn: (teamId, actor = CURRENT_ACTOR) => fire(actor, { type: 'checkIn', teamId }),
      fieldReport: (teamId, to) => fire(teamActor(teamId), { type: 'fieldReport', teamId, to }),
      submitFeedback: (input) => act(teamActor(input.teamId), { type: 'feedback', input }),
      acknowledgeAlert: (alertId) => fire(CURRENT_ACTOR, { type: 'ackAlert', alertId }),
      clearError: () => send({ type: 'clearError' }),
      reset: (data) => send({ type: 'reset', data }),
      demoTick: (script, simStart, now) => send({ type: 'demoTick', script, simStart, now }),
    };
  }, [store, getNow, remote, source]);
  return <StoreContext.Provider value={api}>{children}</StoreContext.Provider>;
}

export function useDispatchStore(): StoreApi {
  const api = useContext(StoreContext);
  if (!api) throw new Error('useDispatchStore must be used inside DispatchStoreProvider');
  return api;
}
