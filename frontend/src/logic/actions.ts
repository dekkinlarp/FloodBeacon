import type { IncidentStatus, TeamStatus } from '../types';
import { INCIDENT_STATUSES, TEAM_STATUSES } from '../types';
import type { DispatchResult, DispatchState } from './dispatch';
import {
  acknowledgeAlert,
  assignTeam,
  checkInTeam,
  confirmHealth,
  recallTeam,
  reportFromField,
  updateIncidentStatus,
  updateTeamStatus,
} from './dispatch';
import type { FeedbackInput } from './feedback';
import { submitFeedback } from './feedback';

// Every change a person can make, as plain data. The browser (demo mode) and
// the API server both run them through `runAction`, so the rules are the same
// wherever the change happens.

export type ActionBody =
  | { type: 'assign'; incidentId: string; teamId: string; backup: boolean }
  | { type: 'incidentStatus'; incidentId: string; to: IncidentStatus }
  | { type: 'teamStatus'; teamId: string; to: TeamStatus }
  | { type: 'recall'; teamId: string }
  | { type: 'confirmHealth'; incidentId: string }
  | { type: 'checkIn'; teamId: string }
  | { type: 'fieldReport'; teamId: string; to: IncidentStatus }
  | { type: 'feedback'; input: FeedbackInput }
  | { type: 'ackAlert'; alertId: string };

export function runAction(state: DispatchState, action: ActionBody, ctx: { now: Date; actor: string }): DispatchResult {
  switch (action.type) {
    case 'assign':
      return assignTeam(state, action.incidentId, action.teamId, ctx, { backup: action.backup });
    case 'incidentStatus':
      return updateIncidentStatus(state, action.incidentId, action.to, ctx);
    case 'teamStatus':
      return updateTeamStatus(state, action.teamId, action.to, ctx);
    case 'recall':
      return recallTeam(state, action.teamId, ctx);
    case 'confirmHealth':
      return confirmHealth(state, action.incidentId, ctx);
    case 'checkIn':
      return checkInTeam(state, action.teamId, ctx);
    case 'fieldReport':
      return reportFromField(state, action.teamId, action.to, ctx);
    case 'feedback':
      return submitFeedback(state, action.input, ctx);
    case 'ackAlert':
      return acknowledgeAlert(state, action.alertId, ctx);
  }
}

const isStr = (v: unknown): v is string => typeof v === 'string' && v.length > 0 && v.length <= 100;

/**
 * Checks an action that arrived over the network. Returns the typed action, or
 * null if its shape is wrong. Field contents are checked again by the rules.
 */
export function parseAction(value: unknown): ActionBody | null {
  if (typeof value !== 'object' || value === null) return null;
  const a = value as Record<string, unknown>;
  switch (a.type) {
    case 'assign':
      return isStr(a.incidentId) && isStr(a.teamId) && typeof a.backup === 'boolean'
        ? { type: 'assign', incidentId: a.incidentId, teamId: a.teamId, backup: a.backup }
        : null;
    case 'incidentStatus':
      return isStr(a.incidentId) && INCIDENT_STATUSES.includes(a.to as IncidentStatus)
        ? { type: 'incidentStatus', incidentId: a.incidentId, to: a.to as IncidentStatus }
        : null;
    case 'teamStatus':
      return isStr(a.teamId) && TEAM_STATUSES.includes(a.to as TeamStatus)
        ? { type: 'teamStatus', teamId: a.teamId, to: a.to as TeamStatus }
        : null;
    case 'recall':
    case 'checkIn':
      return isStr(a.teamId) ? { type: a.type, teamId: a.teamId } : null;
    case 'confirmHealth':
      return isStr(a.incidentId) ? { type: 'confirmHealth', incidentId: a.incidentId } : null;
    case 'fieldReport':
      return isStr(a.teamId) && INCIDENT_STATUSES.includes(a.to as IncidentStatus)
        ? { type: 'fieldReport', teamId: a.teamId, to: a.to as IncidentStatus }
        : null;
    case 'ackAlert':
      return isStr(a.alertId) ? { type: 'ackAlert', alertId: a.alertId } : null;
    case 'feedback': {
      const i = a.input as Record<string, unknown> | null;
      if (typeof i !== 'object' || i === null || !isStr(i.teamId)) return null;
      if (!(i.water_depth_cm === null || typeof i.water_depth_cm === 'number')) return null;
      if (typeof i.route_worked !== 'boolean' || typeof i.blocked_routes !== 'string') return null;
      if (typeof i.people_helped !== 'number' || typeof i.outcome !== 'string') return null;
      if (!(i.photo_ref === null || typeof i.photo_ref === 'string')) return null;
      return { type: 'feedback', input: i as unknown as FeedbackInput };
    }
    default:
      return null;
  }
}

/** Who made the change. Until login exists, only these two forms are accepted. */
export function isValidActor(actor: unknown): actor is string {
  return actor === 'dispatcher' || (typeof actor === 'string' && /^team:[A-Za-z0-9_-]{1,40}$/.test(actor));
}
