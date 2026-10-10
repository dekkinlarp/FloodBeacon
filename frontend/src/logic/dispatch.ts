import type {
  AccessType,
  Assignment,
  AssignmentEndReason,
  AssignmentRole,
  Event,
  EventEntityType,
  DispatchAlert,
  FieldFeedback,
  Health,
  EventType,
  Incident,
  IncidentStatus,
  Team,
  TeamStatus,
  RouteLeg,
  RoutePlan,
  TravelTime,
  Vehicle,
} from '../types';
import { validateHealth, validateIncident } from './validateData';
import { hoursSince } from './contactBadge';
import { BLOCK_ASSIGNMENT_HOURS, CHECK_IN_INTERVAL_MINUTES, SUGGEST_REST_HOURS, fatigue } from './safety';

// Assignment and status rules for the dispatch layer. Every function is pure:
// it takes the current state and returns either a new state plus the events
// it produced (CLAUDE.md rule 6), or the reasons the change was refused.

export interface DispatchState {
  incidents: Incident[];
  /** Sensitive: never copy values from here into events or logs. */
  health: Health[];
  teams: Team[];
  assignments: Assignment[];
  feedback: FieldFeedback[];
  /** Estimated minutes per team/incident pair (fake now; Person 2 later). */
  travelTimes: TravelTime[];
  /** Explicit routes, set when a route changes. Absent = direct by the team's vehicle. */
  routePlans: RoutePlan[];
  alerts: DispatchAlert[];
  /** Append-only. */
  events: Event[];
}

/** A fresh state from loaded data: no assignments, feedback, routes, alerts or events yet. */
export function initialDispatchState(data: {
  incidents: Incident[];
  health: Health[];
  teams: Team[];
  travelTimes: TravelTime[];
}): DispatchState {
  return {
    incidents: data.incidents,
    health: data.health,
    teams: data.teams,
    travelTimes: data.travelTimes,
    assignments: [],
    feedback: [],
    routePlans: [],
    alerts: [],
    events: [],
  };
}

/** Who is acting and when. Passed in so the functions stay pure. */
export interface ActionContext {
  now: Date;
  actor: string;
}

export type DispatchResult =
  | { ok: true; state: DispatchState; events: Event[] }
  | { ok: false; reasons: string[] };

// ---------------------------------------------------------------------------
// Status transitions

/** Incident transitions a dispatcher may make with `updateIncidentStatus`. */
export const INCIDENT_TRANSITIONS: Record<IncidentStatus, readonly IncidentStatus[]> = {
  new: ['verified', 'cancelled'],
  verified: ['assigned'],
  assigned: ['en_route'],
  en_route: ['on_scene', 'could_not_reach'],
  on_scene: ['resolved', 'could_not_reach'],
  could_not_reach: ['verified'],
  resolved: [],
  cancelled: [],
};

/** Statuses an incident leaves only through `assignTeam`, not by hand. */
const SET_BY_ASSIGNMENT: readonly IncidentStatus[] = ['assigned'];

/** Incident statuses in which teams are actively working it. */
const ACTIVE_INCIDENT_STATUSES: readonly IncidentStatus[] = ['assigned', 'en_route', 'on_scene'];

/**
 * Team transitions a dispatcher may make with `updateTeamStatus`. Moves into
 * `en_route` and `returning` happen through assignment, incident status and recall.
 */
export const TEAM_TRANSITIONS: Record<TeamStatus, readonly TeamStatus[]> = {
  available: ['resting', 'off_duty'],
  en_route: ['on_scene'],
  on_scene: [],
  returning: ['available'],
  resting: ['available', 'off_duty'],
  off_duty: ['available'],
};

export function canTransitionIncident(from: IncidentStatus, to: IncidentStatus): boolean {
  return INCIDENT_TRANSITIONS[from].includes(to);
}

export function canTransitionTeam(from: TeamStatus, to: TeamStatus): boolean {
  return TEAM_TRANSITIONS[from].includes(to);
}

/** Next statuses to offer a dispatcher for an incident (excludes ones set by assignment). */
export function nextIncidentStatuses(status: IncidentStatus): IncidentStatus[] {
  return INCIDENT_TRANSITIONS[status].filter((s) => !SET_BY_ASSIGNMENT.includes(s));
}

// ---------------------------------------------------------------------------
// Access fit

/** Which incident access types each vehicle can serve. */
export const VEHICLE_ACCESS: Record<Vehicle, readonly AccessType[]> = {
  truck: ['truck'],
  flat_boat: ['boat_only', 'truck'],
  kayak: ['boat_only', 'truck'],
  on_foot: ['walk_only', 'truck'],
};

export function vehicleCanServe(vehicle: Vehicle, access: AccessType): boolean {
  return VEHICLE_ACCESS[vehicle].includes(access);
}

// ---------------------------------------------------------------------------
// Queries

export function activeAssignmentsForIncident(state: DispatchState, incidentId: string): Assignment[] {
  return state.assignments.filter((a) => a.incident_id === incidentId && a.ended_at === null);
}

export function activeAssignmentForTeam(state: DispatchState, teamId: string): Assignment | undefined {
  return state.assignments.find((a) => a.team_id === teamId && a.ended_at === null);
}

// ---------------------------------------------------------------------------
// canAssign


export interface AssignCheck {
  ok: boolean;
  /** Why the assignment is not allowed. Empty when `ok`. */
  reasons: string[];
  /** Non-blocking safety notes for the confirm dialog. */
  safetyNotes: string[];
}

export interface AssignOptions {
  /** Explicit "add backup": allows a second team on an incident that already has one. */
  backup?: boolean;
}

export function canAssign(
  state: DispatchState,
  incident: Incident,
  team: Team,
  now: Date,
  options: AssignOptions = {},
): AssignCheck {
  const reasons: string[] = [];
  const backup = options.backup === true;
  const active = activeAssignmentsForIncident(state, incident.id);
  const teamBusy = activeAssignmentForTeam(state, team.id);

  if (backup) {
    if (active.length === 0) {
      reasons.push(`${incident.id} has no active team yet; assign a primary team first.`);
    } else if (!ACTIVE_INCIDENT_STATUSES.includes(incident.status)) {
      reasons.push(`Backup can only be added while the incident is assigned, en route or on scene (it is ${incident.status}).`);
    }
  } else if (active.length > 0) {
    reasons.push(`${incident.id} already has an active team (${active.map((a) => a.team_id).join(', ')}). Use "add backup" to send another.`);
  } else if (incident.status !== 'verified') {
    reasons.push(`Only verified incidents can be assigned (${incident.id} is ${incident.status}).`);
  }

  if (teamBusy) {
    const where = teamBusy.incident_id === incident.id ? 'this incident' : teamBusy.incident_id;
    reasons.push(`${team.name} is already assigned to ${where}. Recall it first.`);
  } else if (team.status !== 'available') {
    reasons.push(`${team.name} is ${team.status.replace(/_/g, ' ')}, not available.`);
  }

  if (fatigue(team, now).level === 'block') {
    reasons.push(`${team.name} has been on duty more than ${BLOCK_ASSIGNMENT_HOURS} hours. Rest first.`);
  }

  if (!vehicleCanServe(team.vehicle, incident.access_type)) {
    reasons.push(`${team.name} (${team.vehicle.replace(/_/g, ' ')}) cannot reach ${incident.access_type.replace(/_/g, ' ')} incidents.`);
  }

  return { ok: reasons.length === 0, reasons, safetyNotes: safetyNotes(incident, team, now) };
}

/** Warnings shown before confirming an assignment. They never block it. */
export function safetyNotes(incident: Incident, team: Team, now: Date): string[] {
  const notes: string[] = [];
  if (incident.access_type === 'boat_only' && !team.skills.includes('swimmer')) {
    notes.push('No swimmer on this team for a boat-only incident.');
  }
  if (incident.needs.includes('medical') && !team.skills.includes('first_aid')) {
    notes.push('No first aid skill on this team for a medical incident.');
  }
  if (fatigue(team, now).level === 'rest') {
    notes.push(`Team has been on duty ${SUGGEST_REST_HOURS} hours or more; consider rest.`);
  }
  if (team.last_check_in_at === null) {
    notes.push('Team has never checked in.');
  } else if (hoursSince(team.last_check_in_at, now) * 60 > CHECK_IN_INTERVAL_MINUTES) {
    notes.push(`Team's last check-in was more than ${CHECK_IN_INTERVAL_MINUTES} minutes ago.`);
  }
  if (incident.ai_extracted && !incident.verified_by_human) {
    notes.push('Incident details were extracted by AI and are not yet verified by a person.');
  }
  return notes;
}

// ---------------------------------------------------------------------------
// Changes

/** Builds the next state step by step, collecting one event per change. */
export class Draft {
  state: DispatchState;
  readonly events: Event[] = [];

  constructor(
    initial: DispatchState,
    private readonly ctx: ActionContext,
  ) {
    this.state = { ...initial };
  }

  private get iso() {
    return this.ctx.now.toISOString();
  }

  log(
    entity_type: EventEntityType,
    entity_id: string,
    event_type: EventType,
    from_value: string | null,
    to_value: string | null,
    note: string | null = null,
  ) {
    const n = this.state.events.length + this.events.length + 1;
    this.events.push({
      id: `EVT-${String(n).padStart(4, '0')}`,
      occurred_at: this.iso,
      actor: this.ctx.actor,
      entity_type,
      entity_id,
      event_type,
      from_value,
      to_value,
      note,
    });
  }

  setIncidentStatus(id: string, to: IncidentStatus, note: string | null = null) {
    const incident = this.state.incidents.find((i) => i.id === id)!;
    if (incident.status === to) return;
    this.state.incidents = this.state.incidents.map((i) =>
      i.id === id ? { ...i, status: to, updated_at: this.iso } : i,
    );
    this.log('incident', id, 'status_changed', incident.status, to, note);
  }

  checkIn(teamId: string) {
    const team = this.state.teams.find((t) => t.id === teamId)!;
    this.state.teams = this.state.teams.map((t) => (t.id === teamId ? { ...t, last_check_in_at: this.iso } : t));
    this.log('team', teamId, 'checked_in', team.last_check_in_at, this.iso);
  }

  setTeamStatus(id: string, to: TeamStatus, note: string | null = null) {
    const team = this.state.teams.find((t) => t.id === id)!;
    if (team.status === to) return;
    const on_duty_since =
      to === 'off_duty' ? null : team.status === 'off_duty' ? this.iso : team.on_duty_since;
    this.state.teams = this.state.teams.map((t) =>
      t.id === id ? { ...t, status: to, on_duty_since } : t,
    );
    this.log('team', id, 'status_changed', team.status, to, note);
  }

  addAssignment(incidentId: string, teamId: string, role: AssignmentRole) {
    const id = `ASG-${String(this.state.assignments.length + 1).padStart(4, '0')}`;
    this.state.assignments = [
      ...this.state.assignments,
      {
        id,
        incident_id: incidentId,
        team_id: teamId,
        role,
        assigned_at: this.iso,
        assigned_by: this.ctx.actor,
        ended_at: null,
        end_reason: null,
      },
    ];
    this.log('assignment', id, 'assigned', null, `${teamId} → ${incidentId}`, role);
  }

  endAssignment(assignmentId: string, reason: AssignmentEndReason) {
    const a = this.state.assignments.find((x) => x.id === assignmentId)!;
    this.state.assignments = this.state.assignments.map((x) =>
      x.id === assignmentId ? { ...x, ended_at: this.iso, end_reason: reason } : x,
    );
    this.log(
      'assignment',
      assignmentId,
      reason === 'recalled' ? 'recalled' : 'unassigned',
      `${a.team_id} → ${a.incident_id}`,
      null,
      reason,
    );
  }

  done(): DispatchResult {
    return { ok: true, state: { ...this.state, events: [...this.state.events, ...this.events] }, events: this.events };
  }
}

const fail = (...reasons: string[]): DispatchResult => ({ ok: false, reasons });

/**
 * Assigns a team. A primary assignment moves the incident verified → assigned;
 * a backup leaves the incident status alone. The team goes available → en_route.
 */
export function assignTeam(
  state: DispatchState,
  incidentId: string,
  teamId: string,
  ctx: ActionContext,
  options: AssignOptions = {},
): DispatchResult {
  const incident = state.incidents.find((i) => i.id === incidentId);
  const team = state.teams.find((t) => t.id === teamId);
  if (!incident) return fail(`Unknown incident ${incidentId}.`);
  if (!team) return fail(`Unknown team ${teamId}.`);

  const check = canAssign(state, incident, team, ctx.now, options);
  if (!check.ok) return fail(...check.reasons);

  const d = new Draft(state, ctx);
  const role: AssignmentRole = options.backup ? 'backup' : 'primary';
  d.addAssignment(incidentId, teamId, role);
  if (role === 'primary') d.setIncidentStatus(incidentId, 'assigned');
  d.setTeamStatus(teamId, 'en_route');
  return d.done();
}

/**
 * Moves an incident along `INCIDENT_TRANSITIONS`. Active teams follow:
 * en_route/on_scene are mirrored onto them; resolved and could_not_reach end
 * their assignments and send them to `returning`.
 */
export function updateIncidentStatus(
  state: DispatchState,
  incidentId: string,
  to: IncidentStatus,
  ctx: ActionContext,
): DispatchResult {
  const incident = state.incidents.find((i) => i.id === incidentId);
  if (!incident) return fail(`Unknown incident ${incidentId}.`);
  if (SET_BY_ASSIGNMENT.includes(to)) return fail(`Use "assign team" to move ${incidentId} to ${to}.`);
  if (!canTransitionIncident(incident.status, to)) {
    return fail(`${incidentId} cannot go from ${incident.status} to ${to}.`);
  }

  const d = new Draft(state, ctx);
  d.setIncidentStatus(incidentId, to);
  for (const a of activeAssignmentsForIncident(state, incidentId)) {
    if (to === 'on_scene') {
      d.setTeamStatus(a.team_id, 'on_scene', `incident ${incidentId} on scene`);
    } else if (to === 'resolved' || to === 'could_not_reach') {
      d.endAssignment(a.id, to);
      d.setTeamStatus(a.team_id, 'returning', `incident ${incidentId} ${to}`);
    }
  }
  return d.done();
}

/** Manual team status change along `TEAM_TRANSITIONS`. */
export function updateTeamStatus(
  state: DispatchState,
  teamId: string,
  to: TeamStatus,
  ctx: ActionContext,
): DispatchResult {
  const team = state.teams.find((t) => t.id === teamId);
  if (!team) return fail(`Unknown team ${teamId}.`);
  if (!canTransitionTeam(team.status, to)) {
    return fail(`${team.name} cannot go from ${team.status} to ${to}.`);
  }
  const d = new Draft(state, ctx);
  d.setTeamStatus(teamId, to);
  return d.done();
}

/**
 * Recalls a team from its active assignment: the assignment ends ('recalled')
 * and the team goes to `returning`. If no other team is left on the incident,
 * the incident goes back to `verified` so it can be reassigned.
 */
export function recallTeam(state: DispatchState, teamId: string, ctx: ActionContext): DispatchResult {
  const team = state.teams.find((t) => t.id === teamId);
  if (!team) return fail(`Unknown team ${teamId}.`);
  const assignment = activeAssignmentForTeam(state, teamId);
  if (!assignment) return fail(`${team.name} has no active assignment to recall.`);

  const d = new Draft(state, ctx);
  d.endAssignment(assignment.id, 'recalled');
  d.setTeamStatus(teamId, 'returning', 'recalled');
  const othersLeft = activeAssignmentsForIncident(state, assignment.incident_id).filter(
    (a) => a.id !== assignment.id,
  );
  const incident = state.incidents.find((i) => i.id === assignment.incident_id)!;
  if (othersLeft.length === 0 && ACTIVE_INCIDENT_STATUSES.includes(incident.status)) {
    d.setIncidentStatus(incident.id, 'verified', `${teamId} recalled`);
  }
  return d.done();
}

/**
 * A dispatcher confirms the (possibly AI-extracted) health record. Only the
 * fact of confirmation is logged, never the health values.
 */
export function confirmHealth(state: DispatchState, incidentId: string, ctx: ActionContext): DispatchResult {
  const record = state.health.find((h) => h.incident_id === incidentId);
  if (!record) return fail(`${incidentId} has no health record.`);
  if (record.verified_by_human) return fail(`Health record for ${incidentId} is already confirmed.`);
  const d = new Draft(state, ctx);
  d.state.health = state.health.map((h) =>
    h.incident_id === incidentId ? { ...h, verified_by_human: true, updated_at: ctx.now.toISOString() } : h,
  );
  d.log('health', incidentId, 'verified', 'unconfirmed', 'confirmed');
  return d.done();
}

/** Records a check-in (radio call logged by the dispatcher, or from the team view). */
export function checkInTeam(state: DispatchState, teamId: string, ctx: ActionContext): DispatchResult {
  const team = state.teams.find((t) => t.id === teamId);
  if (!team) return fail(`Unknown team ${teamId}.`);
  if (team.status === 'off_duty') return fail(`${team.name} is off duty.`);
  const d = new Draft(state, ctx);
  d.checkIn(teamId);
  return d.done();
}

/**
 * A field team reports progress on its current incident. Moves the incident
 * (and, through it, the team) and counts as a check-in.
 */
export function reportFromField(
  state: DispatchState,
  teamId: string,
  to: IncidentStatus,
  ctx: ActionContext,
): DispatchResult {
  const assignment = activeAssignmentForTeam(state, teamId);
  if (!assignment) return fail(`${teamId} has no current assignment.`);
  const moved = updateIncidentStatus(state, assignment.incident_id, to, ctx);
  if (!moved.ok) return moved;
  return chain(state, moved, (s) => checkInTeam(s, teamId, ctx));
}

/** Runs `next` on the result of a previous step; returns all events since `start`. */
export function chain(
  start: DispatchState,
  previous: DispatchResult,
  next: (s: DispatchState) => DispatchResult,
): DispatchResult {
  if (!previous.ok) return previous;
  const r = next(previous.state);
  if (!r.ok) return r;
  return { ok: true, state: r.state, events: r.state.events.slice(start.events.length) };
}

/**
 * A new report arrives (e.g. SMS parsed by Person 3's intake). Adds the
 * incident, its optional health record and travel estimates. Health values are
 * never written to the event.
 */
export function reportIncident(
  state: DispatchState,
  report: { incident: Incident; health: Health | null; travelTimes: TravelTime[] },
  ctx: ActionContext,
): DispatchResult {
  const { incident, health } = report;
  const errors = [...validateIncident(incident, `incident[${incident.id}]`)];
  if (health) errors.push(...validateHealth(health, `health[${incident.id}]`));
  if (health && health.incident_id !== incident.id) errors.push('health.incident_id does not match the incident');
  if (state.incidents.some((i) => i.id === incident.id)) errors.push(`${incident.id} already exists.`);
  if (report.travelTimes.some((t) => t.incident_id !== incident.id)) errors.push('travel times must be for the new incident');
  if (errors.length > 0) return fail(...errors);

  const d = new Draft(state, ctx);
  d.state.incidents = [...state.incidents, incident];
  d.log('incident', incident.id, 'created', null, incident.status, `${incident.severity}, ${incident.district}`);
  if (health) {
    d.state.health = [...state.health, health];
    d.log('health', incident.id, 'created', null, null);
  }
  d.state.travelTimes = [...state.travelTimes, ...report.travelTimes];
  return d.done();
}

/** Route for a team to an incident: the explicit plan if any, else one direct leg. */
export function routeFor(state: DispatchState, teamId: string, incidentId: string): RoutePlan | null {
  const plan = state.routePlans.find((p) => p.team_id === teamId && p.incident_id === incidentId);
  if (plan) return plan;
  const team = state.teams.find((t) => t.id === teamId);
  const minutes = state.travelTimes.find((t) => t.team_id === teamId && t.incident_id === incidentId)?.minutes;
  if (!team || minutes === undefined) return null;
  const mode = team.vehicle === 'truck' ? 'truck' : team.vehicle === 'on_foot' ? 'walk' : 'boat';
  return { incident_id: incidentId, team_id: teamId, legs: [{ mode, minutes }], reason: null, updated_at: '' };
}

export function describeLegs(legs: readonly RouteLeg[]): string {
  return legs.map((l) => `${l.mode} ${Math.round(l.minutes)} min`).join(' → ');
}

/**
 * The route for the incident's active teams changes (e.g. bridge closed). Sets
 * the new legs, updates the travel estimate, raises an alert and logs it.
 */
export function changeRoute(
  state: DispatchState,
  change: { incidentId: string; legs: RouteLeg[]; reason: string },
  ctx: ActionContext,
): DispatchResult {
  const active = activeAssignmentsForIncident(state, change.incidentId);
  if (active.length === 0) return fail(`${change.incidentId} has no active team to re-route.`);
  if (change.legs.length === 0 || change.legs.some((l) => !(l.minutes >= 0))) return fail('Route needs legs with minutes >= 0.');

  const d = new Draft(state, ctx);
  const total = change.legs.reduce((sum, l) => sum + l.minutes, 0);
  for (const a of active) {
    const before = routeFor(state, a.team_id, change.incidentId);
    const plan: RoutePlan = {
      incident_id: change.incidentId,
      team_id: a.team_id,
      legs: change.legs,
      reason: change.reason,
      updated_at: ctx.now.toISOString(),
    };
    d.state.routePlans = [
      ...d.state.routePlans.filter((p) => !(p.team_id === a.team_id && p.incident_id === change.incidentId)),
      plan,
    ];
    d.state.travelTimes = [
      ...d.state.travelTimes.filter((t) => !(t.team_id === a.team_id && t.incident_id === change.incidentId)),
      { team_id: a.team_id, incident_id: change.incidentId, minutes: total },
    ];
    const teamName = state.teams.find((t) => t.id === a.team_id)?.name ?? a.team_id;
    d.state.alerts = [
      ...d.state.alerts,
      {
        id: `ALR-${String(d.state.alerts.length + 1).padStart(4, '0')}`,
        created_at: ctx.now.toISOString(),
        message: `Route changed for ${teamName} → ${change.incidentId}: ${change.reason}. Now ${describeLegs(change.legs)}.`,
        incident_id: change.incidentId,
        team_id: a.team_id,
        acknowledged_at: null,
      },
    ];
    d.log(
      'incident',
      change.incidentId,
      'updated',
      before ? describeLegs(before.legs) : null,
      describeLegs(change.legs),
      `route for ${a.team_id}: ${change.reason}`,
    );
  }
  return d.done();
}

/** Dispatcher has seen the alert. */
export function acknowledgeAlert(state: DispatchState, alertId: string, ctx: ActionContext): DispatchResult {
  const alert = state.alerts.find((a) => a.id === alertId);
  if (!alert) return fail(`Unknown alert ${alertId}.`);
  if (alert.acknowledged_at) return fail(`Alert ${alertId} is already acknowledged.`);
  const d = new Draft(state, ctx);
  d.state.alerts = state.alerts.map((a) => (a.id === alertId ? { ...a, acknowledged_at: ctx.now.toISOString() } : a));
  d.log(alert.incident_id ? 'incident' : 'team', alert.incident_id ?? alert.team_id ?? alertId, 'updated', null, null, `alert ${alertId} acknowledged`);
  return d.done();
}

/** One line for the event log. Uses ids and statuses only (never health data). */
export function describeEvent(e: Event): string {
  const what = e.note ? ` (${e.note})` : '';
  switch (e.event_type) {
    case 'status_changed':
      return `${e.entity_id}: ${e.from_value ?? '?'} → ${e.to_value ?? '?'}${what}`;
    case 'assigned':
      return `Assigned ${e.to_value ?? ''}${what}`;
    case 'unassigned':
      return `Assignment ended ${e.from_value ?? ''}${what}`;
    case 'recalled':
      return `Recalled ${e.from_value ?? ''}`;
    case 'checked_in':
      return `${e.entity_id} checked in`;
    case 'created':
      return e.entity_type === 'feedback'
        ? `Field feedback ${e.entity_id}: ${(e.to_value ?? '').replace(/_/g, ' ')}${what}`
        : `${e.entity_type === 'health' ? 'Health record' : e.entity_type} ${e.entity_id} created${what}`;
    case 'updated':
      return e.to_value ? `${e.entity_id}: ${e.from_value ?? 'direct'} ⇒ ${e.to_value}${what}` : `${e.entity_id}${what}`;
    case 'verified':
      return `${e.entity_type === 'health' ? 'Health record' : e.entity_type} ${e.entity_id} confirmed by dispatcher`;
    default:
      return `${e.entity_type} ${e.entity_id}: ${e.event_type}${what}`;
  }
}
