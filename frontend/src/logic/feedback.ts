import type { FeedbackOutcome, FieldFeedback, IncidentStatus } from '../types';
import { FEEDBACK_OUTCOMES } from '../types';
import type { ActionContext, DispatchResult, DispatchState } from './dispatch';
import { Draft, activeAssignmentForTeam, chain, checkInTeam, updateIncidentStatus } from './dispatch';

/** Incident status each outcome leads to. */
export const OUTCOME_STATUS: Record<FeedbackOutcome, IncidentStatus> = {
  evacuated: 'resolved',
  supplied: 'resolved',
  referred_1669: 'resolved',
  no_one_found: 'resolved',
  could_not_reach: 'could_not_reach',
};

/** Outcomes that make sense from the incident's current status. */
export function allowedOutcomes(status: IncidentStatus): FeedbackOutcome[] {
  if (status === 'on_scene') return [...FEEDBACK_OUTCOMES];
  if (status === 'en_route') return ['could_not_reach'];
  return [];
}

export const MAX_WATER_DEPTH_CM = 500;
export const MAX_BLOCKED_ROUTES_CHARS = 500;

export interface FeedbackInput {
  teamId: string;
  water_depth_cm: number | null;
  route_worked: boolean;
  blocked_routes: string;
  people_helped: number;
  outcome: FeedbackOutcome;
  photo_ref: string | null;
}

/** Field-level problems with the form input. Empty means valid. */
export function validateFeedbackInput(input: FeedbackInput): string[] {
  const errors: string[] = [];
  const d = input.water_depth_cm;
  if (d !== null && (!Number.isFinite(d) || d < 0 || d > MAX_WATER_DEPTH_CM)) {
    errors.push(`Water depth must be between 0 and ${MAX_WATER_DEPTH_CM} cm.`);
  }
  if (!Number.isInteger(input.people_helped) || input.people_helped < 0) {
    errors.push('People helped must be a whole number, 0 or more.');
  }
  if (input.blocked_routes.length > MAX_BLOCKED_ROUTES_CHARS) {
    errors.push(`Blocked roads/bridges must be ${MAX_BLOCKED_ROUTES_CHARS} characters or fewer.`);
  }
  if (!FEEDBACK_OUTCOMES.includes(input.outcome)) errors.push('Choose an outcome.');
  if (input.outcome === 'could_not_reach' && input.people_helped > 0) {
    errors.push('People helped must be 0 when the team could not reach the incident.');
  }
  return errors;
}

/**
 * Stores the feedback, moves the incident to the outcome's status (which ends
 * the assignment and sends the team to returning) and records a check-in.
 * Every step writes events.
 */
export function submitFeedback(state: DispatchState, input: FeedbackInput, ctx: ActionContext): DispatchResult {
  const errors = validateFeedbackInput(input);
  if (errors.length > 0) return { ok: false, reasons: errors };

  const assignment = activeAssignmentForTeam(state, input.teamId);
  if (!assignment) return { ok: false, reasons: [`${input.teamId} has no current assignment.`] };
  const incident = state.incidents.find((i) => i.id === assignment.incident_id)!;
  if (!allowedOutcomes(incident.status).includes(input.outcome)) {
    return {
      ok: false,
      reasons: [`Outcome "${input.outcome.replace(/_/g, ' ')}" is not possible while ${incident.id} is ${incident.status.replace(/_/g, ' ')}.`],
    };
  }

  const d = new Draft(state, ctx);
  const id = `FB-${String(state.feedback.length + 1).padStart(4, '0')}`;
  const record: FieldFeedback = {
    id,
    incident_id: incident.id,
    team_id: input.teamId,
    submitted_at: ctx.now.toISOString(),
    submitted_by: ctx.actor,
    water_depth_cm: input.water_depth_cm,
    route_worked: input.route_worked,
    blocked_routes: input.blocked_routes.trim(),
    people_helped: input.people_helped,
    outcome: input.outcome,
    photo_ref: input.photo_ref,
  };
  d.state.feedback = [...state.feedback, record];
  d.log('feedback', id, 'created', null, input.outcome, `${incident.id} by ${input.teamId}`);
  const stored = d.done();

  return chain(
    state,
    chain(state, stored, (s) => updateIncidentStatus(s, incident.id, OUTCOME_STATUS[input.outcome], ctx)),
    (s) => checkInTeam(s, input.teamId, ctx),
  );
}
