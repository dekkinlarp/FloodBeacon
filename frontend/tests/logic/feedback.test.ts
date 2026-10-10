import { describe, expect, it } from 'vitest';
import type { DispatchResult, DispatchState } from '../../src/logic/dispatch';
import { assignTeam, initialDispatchState, updateIncidentStatus } from '../../src/logic/dispatch';
import type { FeedbackInput } from '../../src/logic/feedback';
import { OUTCOME_STATUS, allowedOutcomes, submitFeedback, validateFeedbackInput } from '../../src/logic/feedback';
import { loadFakeData } from '../../src/data/fakeData';
import { FEEDBACK_OUTCOMES } from '../../src/types';

const ctx = { now: new Date('2026-10-02T08:30:00+07:00'), actor: 'team:TEAM-02' };
const fake = loadFakeData();

function ok(r: DispatchResult): DispatchState {
  if (!r.ok) throw new Error(r.reasons.join('; '));
  return r.state;
}

/** INC-001 with TEAM-02 assigned and moved to `status`. */
function stateAt(status: 'assigned' | 'en_route' | 'on_scene'): DispatchState {
  let s: DispatchState = initialDispatchState(fake);
  s = ok(assignTeam(s, 'INC-001', 'TEAM-02', ctx));
  if (status !== 'assigned') s = ok(updateIncidentStatus(s, 'INC-001', 'en_route', ctx));
  if (status === 'on_scene') s = ok(updateIncidentStatus(s, 'INC-001', 'on_scene', ctx));
  return s;
}

const input = (over: Partial<FeedbackInput> = {}): FeedbackInput => ({
  teamId: 'TEAM-02',
  water_depth_cm: 80,
  route_worked: true,
  blocked_routes: '',
  people_helped: 2,
  outcome: 'evacuated',
  photo_ref: null,
  ...over,
});

describe('outcome → incident status', () => {
  it('maps every helped/no-one-found outcome to resolved and could_not_reach to could_not_reach', () => {
    expect(OUTCOME_STATUS).toEqual({
      evacuated: 'resolved',
      supplied: 'resolved',
      referred_1669: 'resolved',
      no_one_found: 'resolved',
      could_not_reach: 'could_not_reach',
    });
  });

  it('allows all outcomes on scene, only could_not_reach en route, none otherwise', () => {
    expect(allowedOutcomes('on_scene')).toEqual([...FEEDBACK_OUTCOMES]);
    expect(allowedOutcomes('en_route')).toEqual(['could_not_reach']);
    expect(allowedOutcomes('assigned')).toEqual([]);
  });
});

describe('validateFeedbackInput', () => {
  it('accepts a normal report', () => {
    expect(validateFeedbackInput(input())).toEqual([]);
    expect(validateFeedbackInput(input({ water_depth_cm: null }))).toEqual([]);
  });

  it('rejects bad depth, people count, long text and helped-but-not-reached', () => {
    expect(validateFeedbackInput(input({ water_depth_cm: -1 }))).toHaveLength(1);
    expect(validateFeedbackInput(input({ water_depth_cm: Number.NaN }))).toHaveLength(1);
    expect(validateFeedbackInput(input({ people_helped: 1.5 }))).toHaveLength(1);
    expect(validateFeedbackInput(input({ blocked_routes: 'x'.repeat(501) }))).toHaveLength(1);
    expect(validateFeedbackInput(input({ outcome: 'could_not_reach', people_helped: 3 }))).toEqual([
      'People helped must be 0 when the team could not reach the incident.',
    ]);
  });
});

describe('submitFeedback', () => {
  it('stores feedback, resolves the incident, frees the team and checks it in — all as events', () => {
    const r = submitFeedback(stateAt('on_scene'), input({ photo_ref: 'IMG_0042.jpg', blocked_routes: '  Soi 20 bridge down ' }), ctx);
    const s = ok(r);
    expect(s.feedback).toEqual([
      expect.objectContaining({
        id: 'FB-0001',
        incident_id: 'INC-001',
        team_id: 'TEAM-02',
        submitted_by: 'team:TEAM-02',
        water_depth_cm: 80,
        blocked_routes: 'Soi 20 bridge down',
        outcome: 'evacuated',
        photo_ref: 'IMG_0042.jpg',
      }),
    ]);
    expect(s.incidents.find((i) => i.id === 'INC-001')!.status).toBe('resolved');
    expect(s.teams.find((t) => t.id === 'TEAM-02')!.status).toBe('returning');
    expect(s.assignments[0]!.end_reason).toBe('resolved');
    expect(r.ok && r.events.map((e) => [e.entity_type, e.event_type])).toEqual([
      ['feedback', 'created'],
      ['incident', 'status_changed'],
      ['assignment', 'unassigned'],
      ['team', 'status_changed'],
      ['team', 'checked_in'],
    ]);
    expect(s.events).toHaveLength(stateAt('on_scene').events.length + 5);
  });

  it('records no_one_found as resolved', () => {
    const s = ok(submitFeedback(stateAt('on_scene'), input({ outcome: 'no_one_found', people_helped: 0 }), ctx));
    expect(s.incidents.find((i) => i.id === 'INC-001')!.status).toBe('resolved');
  });

  it('records could_not_reach from en route', () => {
    const s = ok(submitFeedback(stateAt('en_route'), input({ outcome: 'could_not_reach', people_helped: 0, route_worked: false }), ctx));
    expect(s.incidents.find((i) => i.id === 'INC-001')!.status).toBe('could_not_reach');
    expect(s.teams.find((t) => t.id === 'TEAM-02')!.status).toBe('returning');
  });

  it('refuses a resolved outcome before the team is on scene, and changes nothing', () => {
    const before = stateAt('en_route');
    const r = submitFeedback(before, input(), ctx);
    expect(r).toEqual({ ok: false, reasons: ['Outcome "evacuated" is not possible while INC-001 is en route.'] });
  });

  it('refuses invalid input and teams without an assignment', () => {
    expect(submitFeedback(stateAt('on_scene'), input({ people_helped: -1 }), ctx).ok).toBe(false);
    expect(submitFeedback(stateAt('on_scene'), input({ teamId: 'TEAM-01' }), ctx).ok).toBe(false);
  });
});
