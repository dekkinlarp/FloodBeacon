import type { Health, Incident, IncidentStatus, RouteLeg, TravelTime, Vehicle } from '../types';
import { INCIDENT_STATUSES, ROUTE_MODES, VEHICLES } from '../types';
import type { ActionContext, DispatchResult, DispatchState } from './dispatch';
import {
  activeAssignmentsForIncident,
  assignTeam,
  canAssign,
  changeRoute,
  reportFromField,
  reportIncident,
  updateIncidentStatus,
} from './dispatch';
import type { FeedbackInput } from './feedback';
import { submitFeedback } from './feedback';
import { suggestTeams } from './suggest';

// Replays data/fake/demo_script.json. Each step goes through the same pure
// dispatch functions a person would use, so every step writes events. If the
// dispatcher already did a step by hand, the step is skipped (not an error).

/** Actor for steps that simulate the dispatcher's own clicks. */
export const DEMO_DISPATCHER = 'demo:dispatcher';
/** Actor for incoming reports in the script (stands in for Person 3's SMS intake). */
export const DEMO_INTAKE = 'demo:sms-intake';

interface StepBase {
  id: string;
  /** Minutes after T+0. */
  at_minutes: number;
  label: string;
}

export type DemoStep = StepBase &
  (
    | { type: 'note' }
    | {
        type: 'incident_reported';
        /** Timestamps are filled in with the simulated time when the step runs. */
        incident: Omit<Incident, 'created_at' | 'updated_at' | 'last_contact_at'>;
        health: Omit<Health, 'updated_at'> | null;
        travel_times: TravelTime[];
      }
    | { type: 'verify_incident'; incident_id: string }
    | { type: 'assign_suggested'; incident_id: string; vehicles: Vehicle[] }
    | { type: 'field_report'; incident_id: string; to: IncidentStatus }
    | { type: 'route_change'; incident_id: string; legs: RouteLeg[]; reason: string }
    | { type: 'feedback'; incident_id: string; feedback: Omit<FeedbackInput, 'teamId'> }
  );

export interface DemoScript {
  version: 1;
  title: string;
  description: string;
  steps: DemoStep[];
}

const STEP_TYPES = ['note', 'incident_reported', 'verify_incident', 'assign_suggested', 'field_report', 'route_change', 'feedback'];

/** Structural checks on the script file. Record contents are checked again when applied. */
export function validateDemoScript(value: unknown): string[] {
  const errors: string[] = [];
  const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);
  if (!isObj(value)) return ['script: expected object'];
  if (value.version !== 1) errors.push('script.version: expected 1');
  if (!Array.isArray(value.steps)) return [...errors, 'script.steps: expected array'];
  const ids = new Set<unknown>();
  let last = -Infinity;
  value.steps.forEach((s, i) => {
    const w = `steps[${i}]`;
    if (!isObj(s)) return errors.push(`${w}: expected object`);
    if (typeof s.id !== 'string' || s.id === '') errors.push(`${w}.id: expected string`);
    if (ids.has(s.id)) errors.push(`${w}.id: duplicate ${String(s.id)}`);
    ids.add(s.id);
    if (typeof s.at_minutes !== 'number' || !(s.at_minutes >= 0)) errors.push(`${w}.at_minutes: expected number >= 0`);
    else if (s.at_minutes < last) errors.push(`${w}.at_minutes: steps must be in time order`);
    else last = s.at_minutes;
    if (typeof s.label !== 'string') errors.push(`${w}.label: expected string`);
    if (!STEP_TYPES.includes(s.type as string)) return errors.push(`${w}.type: unknown ${String(s.type)}`);
    if (s.type !== 'note' && s.type !== 'incident_reported' && typeof s.incident_id !== 'string') {
      errors.push(`${w}.incident_id: expected string`);
    }
    if (s.type === 'incident_reported' && (!isObj(s.incident) || !Array.isArray(s.travel_times))) {
      errors.push(`${w}: needs incident and travel_times`);
    }
    if (s.type === 'assign_suggested' && (!Array.isArray(s.vehicles) || s.vehicles.some((v) => !VEHICLES.includes(v)))) {
      errors.push(`${w}.vehicles: expected vehicle list`);
    }
    if (s.type === 'field_report' && !INCIDENT_STATUSES.includes(s.to as IncidentStatus)) errors.push(`${w}.to: unknown status`);
    if (s.type === 'route_change') {
      const legs = s.legs;
      if (!Array.isArray(legs) || legs.length === 0 || legs.some((l) => !isObj(l) || !ROUTE_MODES.includes(l.mode as never) || !(Number(l.minutes) >= 0))) {
        errors.push(`${w}.legs: expected [{ mode, minutes }]`);
      }
      if (typeof s.reason !== 'string') errors.push(`${w}.reason: expected string`);
    }
    if (s.type === 'feedback' && !isObj(s.feedback)) errors.push(`${w}.feedback: expected object`);
  });
  return errors;
}

/** Steps whose time has come and that have not run yet, in script order. */
export function dueSteps(script: DemoScript, done: ReadonlySet<string>, elapsedMinutes: number): DemoStep[] {
  return script.steps.filter((s) => s.at_minutes <= elapsedMinutes && !done.has(s.id));
}

export type StepOutcome =
  | { kind: 'applied'; state: DispatchState; message: string }
  | { kind: 'skipped'; message: string }
  | { kind: 'failed'; message: string };

const ORDER: readonly IncidentStatus[] = ['new', 'verified', 'assigned', 'en_route', 'on_scene', 'resolved'];

function teamOn(state: DispatchState, incidentId: string): string | null {
  const active = activeAssignmentsForIncident(state, incidentId);
  return (active.find((a) => a.role === 'primary') ?? active[0])?.team_id ?? null;
}

function result(r: DispatchResult, message: string): StepOutcome {
  return r.ok ? { kind: 'applied', state: r.state, message } : { kind: 'failed', message: r.reasons.join(' ') };
}

/** Applies one step at simulated time `now`. Never throws for state conflicts. */
export function applyDemoStep(state: DispatchState, step: DemoStep, now: Date): StepOutcome {
  const ctx = (actor: string): ActionContext => ({ now, actor });
  const iso = now.toISOString();
  const incident = 'incident_id' in step ? state.incidents.find((i) => i.id === step.incident_id) : undefined;
  if ('incident_id' in step && !incident) return { kind: 'skipped', message: `${step.incident_id} does not exist yet.` };

  switch (step.type) {
    case 'note':
      return { kind: 'skipped', message: step.label };

    case 'incident_reported': {
      if (state.incidents.some((i) => i.id === step.incident.id)) {
        return { kind: 'skipped', message: `${step.incident.id} already exists.` };
      }
      const full: Incident = { ...step.incident, created_at: iso, updated_at: iso, last_contact_at: iso };
      const health: Health | null = step.health ? { ...step.health, updated_at: iso } : null;
      return result(
        reportIncident(state, { incident: full, health, travelTimes: step.travel_times }, ctx(DEMO_INTAKE)),
        `${full.id} reported (${full.severity}, ${full.district}).`,
      );
    }

    case 'verify_incident':
      if (incident!.status !== 'new') return { kind: 'skipped', message: `${incident!.id} is already ${incident!.status}.` };
      return result(updateIncidentStatus(state, incident!.id, 'verified', ctx(DEMO_DISPATCHER)), `${incident!.id} verified.`);

    case 'assign_suggested': {
      const existing = teamOn(state, incident!.id);
      if (existing) return { kind: 'skipped', message: `${incident!.id} already has ${existing}.` };
      const pick = suggestTeams(incident!, state.teams, state.travelTimes, now).find(
        (s) => step.vehicles.includes(s.team.vehicle) && canAssign(state, incident!, s.team, now).ok,
      );
      if (!pick) return { kind: 'skipped', message: `No suitable ${step.vehicles.join('/')} team is free for ${incident!.id}.` };
      return result(
        assignTeam(state, incident!.id, pick.team.id, ctx(DEMO_DISPATCHER)),
        `${pick.team.name} assigned to ${incident!.id} (top suggestion, score ${pick.score}).`,
      );
    }

    case 'field_report': {
      const team = teamOn(state, incident!.id);
      if (!team) return { kind: 'skipped', message: `${incident!.id} has no team.` };
      if (ORDER.indexOf(incident!.status) >= ORDER.indexOf(step.to)) {
        return { kind: 'skipped', message: `${incident!.id} is already ${incident!.status}.` };
      }
      return result(reportFromField(state, team, step.to, ctx(`team:${team}`)), `${team}: ${incident!.id} ${step.to.replace(/_/g, ' ')}.`);
    }

    case 'route_change':
      if (!teamOn(state, incident!.id)) return { kind: 'skipped', message: `${incident!.id} has no team to re-route.` };
      return result(
        changeRoute(state, { incidentId: incident!.id, legs: step.legs, reason: step.reason }, ctx(DEMO_DISPATCHER)),
        `Route changed for ${incident!.id}: ${step.reason}.`,
      );

    case 'feedback': {
      const team = teamOn(state, incident!.id);
      if (!team) return { kind: 'skipped', message: `${incident!.id} has no team to report.` };
      return result(
        submitFeedback(state, { ...step.feedback, teamId: team }, ctx(`team:${team}`)),
        `${team} sent feedback: ${step.feedback.outcome.replace(/_/g, ' ')}.`,
      );
    }
  }
}

export interface DemoLogEntry {
  stepId: string;
  label: string;
  at: string;
  kind: StepOutcome['kind'];
  message: string;
}

/**
 * Runs every due step in order. Each step runs at its own scripted time (or
 * `now` if that is earlier), so a big clock jump still gives correct timestamps.
 */
export function runDueSteps(
  state: DispatchState,
  script: DemoScript,
  done: ReadonlySet<string>,
  simStart: number,
  now: number,
): { state: DispatchState; log: DemoLogEntry[] } {
  let current = state;
  const log: DemoLogEntry[] = [];
  for (const step of dueSteps(script, done, (now - simStart) / 60_000)) {
    const at = new Date(Math.min(now, simStart + step.at_minutes * 60_000));
    const outcome = applyDemoStep(current, step, at);
    if (outcome.kind === 'applied') current = outcome.state;
    log.push({ stepId: step.id, label: step.label, at: at.toISOString(), kind: outcome.kind, message: outcome.message });
  }
  return { state: current, log };
}
