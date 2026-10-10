import { describe, expect, it } from 'vitest';
import type { DispatchResult, DispatchState } from '../../src/logic/dispatch';
import {
  INCIDENT_TRANSITIONS,
  acknowledgeAlert,
  changeRoute,
  describeLegs,
  reportIncident,
  routeFor,
  assignTeam,
  canAssign,
  canTransitionIncident,
  checkInTeam,
  confirmHealth,
  initialDispatchState,
  reportFromField,
  describeEvent,
  nextIncidentStatuses,
  recallTeam,
  safetyNotes,
  updateIncidentStatus,
  updateTeamStatus,
  vehicleCanServe,
} from '../../src/logic/dispatch';
import { loadFakeData } from '../../src/data/fakeData';
import type { Incident, IncidentStatus, Team } from '../../src/types';
import { INCIDENT_STATUSES } from '../../src/types';

// Fixed clock: just after the fake data's latest timestamps, so no fatigue or
// check-in notes fire unless a test sets them up.
const ctx = { now: new Date('2026-10-02T08:30:00+07:00'), actor: 'dispatcher-test' };
const fake = loadFakeData();

/**
 * INC-001 verified boat_only (medical) · INC-003 new walk_only · INC-005 verified truck
 * TEAM-01 truck · TEAM-02/03 flat_boat · TEAM-04 kayak · TEAM-05 on_foot (resting) · TEAM-06 truck (off_duty)
 */
function initialState(): DispatchState {
  return initialDispatchState(fake);
}

function ok(result: DispatchResult): DispatchState {
  if (!result.ok) throw new Error(`expected ok, got: ${result.reasons.join('; ')}`);
  return result.state;
}

const incident = (s: DispatchState, id: string) => s.incidents.find((i) => i.id === id)!;
const team = (s: DispatchState, id: string) => s.teams.find((t) => t.id === id)!;

/** INC-001 with TEAM-02 as primary, moved on to `status`. */
function assignedState(status: 'assigned' | 'en_route' | 'on_scene' = 'assigned'): DispatchState {
  let s = ok(assignTeam(initialState(), 'INC-001', 'TEAM-02', ctx));
  if (status !== 'assigned') s = ok(updateIncidentStatus(s, 'INC-001', 'en_route', ctx));
  if (status === 'on_scene') s = ok(updateIncidentStatus(s, 'INC-001', 'on_scene', ctx));
  return s;
}

describe('incident status transitions', () => {
  const allowed: [IncidentStatus, IncidentStatus][] = [
    ['new', 'verified'],
    ['verified', 'assigned'],
    ['assigned', 'en_route'],
    ['en_route', 'on_scene'],
    ['on_scene', 'resolved'],
    ['en_route', 'could_not_reach'],
    ['on_scene', 'could_not_reach'],
    ['could_not_reach', 'verified'],
    ['new', 'cancelled'],
  ];

  it('allows exactly the transitions in the brief', () => {
    const all = INCIDENT_STATUSES.flatMap((from) =>
      INCIDENT_STATUSES.filter((to) => canTransitionIncident(from, to)).map((to) => [from, to]),
    );
    expect(new Set(all.map(String))).toEqual(new Set(allowed.map(String)));
  });

  it('treats resolved and cancelled as final', () => {
    expect(INCIDENT_TRANSITIONS.resolved).toEqual([]);
    expect(INCIDENT_TRANSITIONS.cancelled).toEqual([]);
  });

  it('rejects invalid transitions and leaves state unchanged', () => {
    const s = initialState();
    for (const [id, to] of [
      ['INC-001', 'resolved'], // verified → resolved
      ['INC-003', 'en_route'], // new → en_route
      ['INC-001', 'cancelled'], // verified → cancelled (only new → cancelled)
      ['INC-017', 'verified'], // cancelled → verified
    ] as const) {
      const r = updateIncidentStatus(s, id, to, ctx);
      expect(r.ok, `${id} → ${to}`).toBe(false);
    }
  });

  it('does not allow setting "assigned" by hand', () => {
    const r = updateIncidentStatus(initialState(), 'INC-001', 'assigned', ctx);
    expect(r).toEqual({ ok: false, reasons: [expect.stringContaining('assign team')] });
    expect(nextIncidentStatuses('verified')).toEqual([]);
  });

  it('accepts a valid transition and writes one event', () => {
    const r = updateIncidentStatus(initialState(), 'INC-003', 'verified', ctx);
    const s = ok(r);
    expect(incident(s, 'INC-003').status).toBe('verified');
    expect(incident(s, 'INC-003').updated_at).toBe(ctx.now.toISOString());
    expect(r.ok && r.events).toEqual([
      expect.objectContaining({
        entity_type: 'incident',
        entity_id: 'INC-003',
        event_type: 'status_changed',
        from_value: 'new',
        to_value: 'verified',
        actor: 'dispatcher-test',
        occurred_at: ctx.now.toISOString(),
      }),
    ]);
    expect(s.events).toEqual(r.ok ? r.events : []);
  });

  it('rejects an unknown incident', () => {
    expect(updateIncidentStatus(initialState(), 'INC-999', 'verified', ctx).ok).toBe(false);
  });
});

describe('assignTeam', () => {
  it('assigns a primary team: incident → assigned, team → en_route, three events', () => {
    const r = assignTeam(initialState(), 'INC-001', 'TEAM-02', ctx);
    const s = ok(r);
    expect(incident(s, 'INC-001').status).toBe('assigned');
    expect(team(s, 'TEAM-02').status).toBe('en_route');
    expect(s.assignments).toEqual([
      expect.objectContaining({ incident_id: 'INC-001', team_id: 'TEAM-02', role: 'primary', ended_at: null }),
    ]);
    expect(r.ok && r.events.map((e) => [e.entity_type, e.event_type, e.to_value])).toEqual([
      ['assignment', 'assigned', 'TEAM-02 → INC-001'],
      ['incident', 'status_changed', 'assigned'],
      ['team', 'status_changed', 'en_route'],
    ]);
  });

  it('gives events unique, increasing ids across actions', () => {
    const s = ok(updateIncidentStatus(assignedState(), 'INC-001', 'en_route', ctx));
    const ids = s.events.map((e) => e.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids).toEqual([...ids].sort());
  });

  it('does not mutate the input state', () => {
    const s = initialState();
    const before = JSON.stringify(s);
    assignTeam(s, 'INC-001', 'TEAM-02', ctx);
    expect(JSON.stringify(s)).toBe(before);
  });

  it('only assigns verified incidents', () => {
    const r = assignTeam(initialState(), 'INC-003', 'TEAM-05', ctx); // INC-003 is new
    expect(r.ok).toBe(false);
    expect(!r.ok && r.reasons).toContainEqual(expect.stringContaining('Only verified'));
  });
});

describe('rule: one active team per incident unless "add backup" is explicit', () => {
  it('refuses a second primary team', () => {
    const r = assignTeam(assignedState(), 'INC-001', 'TEAM-03', ctx);
    expect(r.ok).toBe(false);
    expect(!r.ok && r.reasons.join()).toContain('already has an active team (TEAM-02)');
  });

  it('allows a second team as an explicit backup without changing the incident status', () => {
    const before = assignedState('en_route');
    const r = assignTeam(before, 'INC-001', 'TEAM-03', ctx, { backup: true });
    const s = ok(r);
    expect(s.assignments.filter((a) => a.ended_at === null).map((a) => [a.team_id, a.role])).toEqual([
      ['TEAM-02', 'primary'],
      ['TEAM-03', 'backup'],
    ]);
    expect(incident(s, 'INC-001').status).toBe('en_route');
    expect(r.ok && r.events.map((e) => e.entity_type)).toEqual(['assignment', 'team']);
  });

  it('refuses a backup when there is no primary yet', () => {
    const r = assignTeam(initialState(), 'INC-001', 'TEAM-03', ctx, { backup: true });
    expect(!r.ok && r.reasons.join()).toContain('no active team yet');
  });
});

describe('rule: a busy team cannot be assigned again until recalled', () => {
  it('refuses a team that has an active assignment', () => {
    const s = ok(assignTeam(initialState(), 'INC-005', 'TEAM-01', ctx));
    const r = assignTeam(s, 'INC-001', 'TEAM-01', ctx); // also blocked by access; check busy reason
    expect(!r.ok && r.reasons).toContainEqual('Truck 1 is already assigned to INC-005. Recall it first.');
  });

  it('refuses a busy team even as a backup on another incident', () => {
    let s = ok(assignTeam(initialState(), 'INC-001', 'TEAM-02', ctx));
    s = ok(updateIncidentStatus(s, 'INC-003', 'verified', ctx));
    const r = assignTeam(s, 'INC-001', 'TEAM-02', ctx, { backup: true });
    expect(!r.ok && r.reasons.join()).toContain('already assigned to this incident');
  });

  it('refuses a team that is resting, off duty or returning', () => {
    const s = initialState();
    expect(canAssign(s, incident(s, 'INC-005'), team(s, 'TEAM-06'), ctx.now).reasons).toContainEqual(
      'Truck 2 is off duty, not available.',
    );
    const v = ok(updateIncidentStatus(s, 'INC-003', 'verified', ctx));
    expect(canAssign(v, incident(v, 'INC-003'), team(v, 'TEAM-05'), ctx.now).reasons).toContainEqual(
      'Walking Team 1 is resting, not available.',
    );
  });

  it('allows the team again only after recall and returning → available', () => {
    let s = assignedState('en_route');
    s = ok(recallTeam(s, 'TEAM-02', ctx));
    expect(team(s, 'TEAM-02').status).toBe('returning');
    expect(assignTeam(s, 'INC-005', 'TEAM-02', ctx).ok).toBe(false); // still returning
    s = ok(updateTeamStatus(s, 'TEAM-02', 'available', ctx));
    expect(assignTeam(s, 'INC-005', 'TEAM-02', ctx).ok).toBe(true);
  });
});

describe('recallTeam', () => {
  it('ends the assignment as recalled and returns the incident to verified when no team is left', () => {
    const r = recallTeam(assignedState('on_scene'), 'TEAM-02', ctx);
    const s = ok(r);
    expect(s.assignments[0]).toMatchObject({ ended_at: ctx.now.toISOString(), end_reason: 'recalled' });
    expect(team(s, 'TEAM-02').status).toBe('returning');
    expect(incident(s, 'INC-001').status).toBe('verified');
    expect(r.ok && r.events.map((e) => [e.entity_type, e.event_type])).toEqual([
      ['assignment', 'recalled'],
      ['team', 'status_changed'],
      ['incident', 'status_changed'],
    ]);
  });

  it('keeps the incident status while another team is still on it', () => {
    let s = assignedState('en_route');
    s = ok(assignTeam(s, 'INC-001', 'TEAM-03', ctx, { backup: true }));
    s = ok(recallTeam(s, 'TEAM-02', ctx));
    expect(incident(s, 'INC-001').status).toBe('en_route');
  });

  it('refuses when the team has no active assignment', () => {
    expect(recallTeam(initialState(), 'TEAM-01', ctx).ok).toBe(false);
  });
});

describe('linked team status', () => {
  it('moves active teams on scene with the incident', () => {
    let s = assignedState('en_route');
    s = ok(assignTeam(s, 'INC-001', 'TEAM-04', ctx, { backup: true }));
    s = ok(updateIncidentStatus(s, 'INC-001', 'on_scene', ctx));
    expect([team(s, 'TEAM-02').status, team(s, 'TEAM-04').status]).toEqual(['on_scene', 'on_scene']);
  });

  it.each(['resolved', 'could_not_reach'] as const)(
    '%s ends assignments and sends teams to returning',
    (to) => {
      const s = ok(updateIncidentStatus(assignedState('on_scene'), 'INC-001', to, ctx));
      expect(incident(s, 'INC-001').status).toBe(to);
      expect(s.assignments[0]).toMatchObject({ end_reason: to });
      expect(team(s, 'TEAM-02').status).toBe('returning');
    },
  );

  it('could_not_reach → verified allows reassignment', () => {
    let s = ok(updateIncidentStatus(assignedState('en_route'), 'INC-001', 'could_not_reach', ctx));
    s = ok(updateIncidentStatus(s, 'INC-001', 'verified', ctx));
    expect(assignTeam(s, 'INC-001', 'TEAM-03', ctx).ok).toBe(true);
  });
});

describe('updateTeamStatus', () => {
  it('allows manual rest / duty changes and records on-duty time', () => {
    let s = ok(updateTeamStatus(initialState(), 'TEAM-06', 'available', ctx));
    expect(team(s, 'TEAM-06').on_duty_since).toBe(ctx.now.toISOString());
    s = ok(updateTeamStatus(s, 'TEAM-06', 'off_duty', ctx));
    expect(team(s, 'TEAM-06').on_duty_since).toBeNull();
    expect(s.events.map((e) => e.to_value)).toEqual(['available', 'off_duty']);
  });

  it('rejects invalid team transitions', () => {
    const s = initialState();
    expect(updateTeamStatus(s, 'TEAM-01', 'en_route', ctx).ok).toBe(false); // only via assignment
    expect(updateTeamStatus(s, 'TEAM-01', 'returning', ctx).ok).toBe(false);
    expect(updateTeamStatus(s, 'TEAM-06', 'resting', ctx).ok).toBe(false); // off_duty → resting
    expect(updateTeamStatus(assignedState(), 'TEAM-02', 'off_duty', ctx).ok).toBe(false); // busy
  });
});

describe('access fit (blocking)', () => {
  it('maps vehicles to the access types they can serve', () => {
    expect(vehicleCanServe('truck', 'truck')).toBe(true);
    expect(vehicleCanServe('truck', 'boat_only')).toBe(false);
    expect(vehicleCanServe('truck', 'walk_only')).toBe(false);
    expect(vehicleCanServe('kayak', 'boat_only')).toBe(true);
    expect(vehicleCanServe('flat_boat', 'walk_only')).toBe(false);
    expect(vehicleCanServe('on_foot', 'walk_only')).toBe(true);
    expect(vehicleCanServe('on_foot', 'boat_only')).toBe(false);
  });

  it('refuses a truck for a boat-only incident', () => {
    const r = assignTeam(initialState(), 'INC-001', 'TEAM-01', ctx);
    expect(!r.ok && r.reasons).toEqual(['Truck 1 (truck) cannot reach boat only incidents.']);
  });
});

describe('safety notes (non-blocking)', () => {
  const base = fake.incidents.find((i) => i.id === 'INC-001')!; // boat_only, medical, verified
  const boat: Team = fake.teams.find((t) => t.id === 'TEAM-02')!; // swimmer + first aid

  it('is empty for a well-matched, rested, recently checked-in team', () => {
    expect(safetyNotes(base, boat, ctx.now)).toEqual([]);
  });

  it('flags skill gaps', () => {
    const noSkills = { ...boat, skills: ['boat_operator' as const] };
    expect(safetyNotes(base, noSkills, ctx.now)).toEqual([
      'No swimmer on this team for a boat-only incident.',
      'No first aid skill on this team for a medical incident.',
    ]);
  });

  it('flags fatigue after 12 hours on duty', () => {
    const tired = { ...boat, on_duty_since: '2026-10-01T20:00:00+07:00' };
    expect(safetyNotes(base, tired, ctx.now)).toEqual(['Team has been on duty 12 hours or more; consider rest.']);
  });

  it('flags an overdue or missing check-in', () => {
    expect(safetyNotes(base, { ...boat, last_check_in_at: '2026-10-02T07:00:00+07:00' }, ctx.now)).toEqual([
      "Team's last check-in was more than 60 minutes ago.",
    ]);
    expect(safetyNotes(base, { ...boat, last_check_in_at: null }, ctx.now)).toEqual([
      'Team has never checked in.',
    ]);
  });

  it('flags unverified AI-extracted incidents', () => {
    const unverified: Incident = { ...base, ai_extracted: true, verified_by_human: false };
    expect(safetyNotes(unverified, boat, ctx.now)).toEqual([
      'Incident details were extracted by AI and are not yet verified by a person.',
    ]);
  });

  it('does not block assignment', () => {
    const s = initialState();
    const tired = { ...boat, on_duty_since: '2026-10-01T19:00:00+07:00' }; // 13.5 h: rest, not block
    const check = canAssign({ ...s, teams: [tired] }, base, tired, ctx.now);
    expect(check.ok).toBe(true);
    expect(check.safetyNotes.length).toBeGreaterThan(0);
  });
});

describe('describeEvent', () => {
  it('describes status changes and assignments without health data', () => {
    const r = assignTeam(initialState(), 'INC-001', 'TEAM-02', ctx);
    expect(r.ok && r.events.map(describeEvent)).toEqual([
      'Assigned TEAM-02 → INC-001 (primary)',
      'INC-001: verified → assigned',
      'TEAM-02: available → en_route',
    ]);
  });
});

describe('confirmHealth', () => {
  it('marks an AI-extracted health record as confirmed and logs it without health values', () => {
    const r = confirmHealth(initialState(), 'INC-006', ctx); // ai_extracted, not verified
    const s = ok(r);
    expect(s.health.find((h) => h.incident_id === 'INC-006')!.verified_by_human).toBe(true);
    expect(r.ok && r.events).toEqual([
      expect.objectContaining({
        entity_type: 'health',
        entity_id: 'INC-006',
        event_type: 'verified',
        from_value: 'unconfirmed',
        to_value: 'confirmed',
        note: null,
      }),
    ]);
    const logged = JSON.stringify(r.ok && r.events);
    expect(logged).not.toContain('insulin');
    expect(describeEvent(r.ok ? r.events[0]! : ({} as never))).toBe('Health record INC-006 confirmed by dispatcher');
  });

  it('refuses a missing or already confirmed record', () => {
    expect(confirmHealth(initialState(), 'INC-003', ctx).ok).toBe(false);
    expect(confirmHealth(initialState(), 'INC-001', ctx).ok).toBe(false);
  });
});

describe('fatigue limit blocks new assignments', () => {
  it('refuses a team on duty more than 16 hours and allows one at exactly 16', () => {
    const s = initialState();
    const inc = incident(s, 'INC-005'); // verified, truck access
    const base = team(s, 'TEAM-01');
    const at = (h: number) => new Date(ctx.now.getTime() - h * 3_600_000).toISOString();
    const tired = { ...base, on_duty_since: at(16.5) };
    expect(canAssign({ ...s, teams: [tired] }, inc, tired, ctx.now).reasons).toEqual([
      'Truck 1 has been on duty more than 16 hours. Rest first.',
    ]);
    const limit = { ...base, on_duty_since: at(16) };
    expect(canAssign({ ...s, teams: [limit] }, inc, limit, ctx.now).ok).toBe(true);
  });
});

describe('checkInTeam', () => {
  it('sets last_check_in_at to now and logs a checked_in event', () => {
    const r = checkInTeam(initialState(), 'TEAM-03', ctx);
    const s = ok(r);
    expect(team(s, 'TEAM-03').last_check_in_at).toBe(ctx.now.toISOString());
    expect(r.ok && r.events.map((e) => [e.entity_type, e.entity_id, e.event_type])).toEqual([
      ['team', 'TEAM-03', 'checked_in'],
    ]);
    expect(describeEvent(r.ok ? r.events[0]! : ({} as never))).toBe('TEAM-03 checked in');
  });

  it('refuses off-duty and unknown teams', () => {
    expect(checkInTeam(initialState(), 'TEAM-06', ctx).ok).toBe(false);
    expect(checkInTeam(initialState(), 'TEAM-99', ctx).ok).toBe(false);
  });
});

describe('reportFromField', () => {
  it("moves the team's incident and counts as a check-in", () => {
    const r = reportFromField(assignedState(), 'TEAM-02', 'en_route', ctx);
    const s = ok(r);
    expect(incident(s, 'INC-001').status).toBe('en_route');
    expect(team(s, 'TEAM-02').last_check_in_at).toBe(ctx.now.toISOString());
    expect(r.ok && r.events.map((e) => e.event_type)).toEqual(['status_changed', 'checked_in']);
  });

  it('rejects invalid transitions and teams without an assignment', () => {
    expect(reportFromField(assignedState(), 'TEAM-02', 'resolved', ctx).ok).toBe(false);
    expect(reportFromField(initialState(), 'TEAM-01', 'en_route', ctx).ok).toBe(false);
  });
});

describe('reportIncident', () => {
  const newIncident = { ...fake.incidents[0]!, id: 'INC-900', status: 'new' as const };

  it('adds the incident, health and travel times with events but no health values', () => {
    const health = { ...fake.health[0]!, incident_id: 'INC-900' };
    const r = reportIncident(initialState(), { incident: newIncident, health, travelTimes: [{ team_id: 'TEAM-01', incident_id: 'INC-900', minutes: 9 }] }, ctx);
    const s = ok(r);
    expect(s.incidents.at(-1)!.id).toBe('INC-900');
    expect(s.health.at(-1)!.incident_id).toBe('INC-900');
    expect(s.travelTimes.at(-1)).toEqual({ team_id: 'TEAM-01', incident_id: 'INC-900', minutes: 9 });
    expect(r.ok && r.events.map((e) => [e.entity_type, e.event_type, e.from_value, e.to_value])).toEqual([
      ['incident', 'created', null, 'new'],
      ['health', 'created', null, null],
    ]);
  });

  it('refuses duplicates and invalid records', () => {
    expect(reportIncident(initialState(), { incident: fake.incidents[0]!, health: null, travelTimes: [] }, ctx).ok).toBe(false);
    expect(reportIncident(initialState(), { incident: { ...newIncident, severity: 'extreme' as never }, health: null, travelTimes: [] }, ctx).ok).toBe(false);
  });
});

describe('changeRoute and alerts', () => {
  it('re-routes the active team, updates travel time, raises an alert and logs it', () => {
    const r = changeRoute(assignedState('en_route'), { incidentId: 'INC-001', legs: [{ mode: 'truck', minutes: 20 }, { mode: 'boat', minutes: 15 }], reason: 'bridge closed' }, ctx);
    const s = ok(r);
    expect(routeFor(s, 'TEAM-02', 'INC-001')!.legs).toHaveLength(2);
    expect(s.travelTimes.find((t) => t.team_id === 'TEAM-02' && t.incident_id === 'INC-001')!.minutes).toBe(35);
    expect(s.alerts).toEqual([expect.objectContaining({ id: 'ALR-0001', incident_id: 'INC-001', team_id: 'TEAM-02', acknowledged_at: null })]);
    expect(r.ok && r.events.map((e) => [e.event_type, e.to_value])).toEqual([['updated', 'truck 20 min → boat 15 min']]);
  });

  it('describes the default route as one direct leg by the team vehicle', () => {
    expect(routeFor(initialState(), 'TEAM-02', 'INC-001')!.legs).toEqual([{ mode: 'boat', minutes: 327 }]);
    expect(describeLegs([{ mode: 'truck', minutes: 25.4 }])).toBe('truck 25 min');
  });

  it('refuses to re-route an incident with no team', () => {
    expect(changeRoute(initialState(), { incidentId: 'INC-001', legs: [{ mode: 'boat', minutes: 5 }], reason: 'x' }, ctx).ok).toBe(false);
  });

  it('acknowledges an alert once, with an event', () => {
    const s = ok(changeRoute(assignedState(), { incidentId: 'INC-001', legs: [{ mode: 'boat', minutes: 5 }], reason: 'x' }, ctx));
    const r = acknowledgeAlert(s, 'ALR-0001', ctx);
    expect(ok(r).alerts[0]!.acknowledged_at).toBe(ctx.now.toISOString());
    expect(r.ok && r.events[0]!.note).toBe('alert ALR-0001 acknowledged');
    expect(acknowledgeAlert(ok(r), 'ALR-0001', ctx).ok).toBe(false);
  });
});
