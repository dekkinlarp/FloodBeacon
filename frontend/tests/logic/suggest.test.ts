import { describe, expect, it } from 'vitest';
import type { Incident, Team, TravelTime } from '../../src/types';
import {
  FATIGUE_FREE_HOURS,
  FATIGUE_PENALTY_PER_HOUR,
  LANGUAGE_BONUS,
  MAX_HOURS_ON_DUTY,
  SKILL_MATCH_BONUS,
  TRAVEL_MAX_POINTS,
  TRAVEL_ZERO_AT_MINUTES,
  evaluateTeam,
  evaluateTeams,
  suggestTeams,
} from '../../src/logic/suggest';
import { loadFakeData } from '../../src/data/fakeData';

const now = new Date('2026-10-02T12:00:00+07:00');
const hoursAgo = (h: number) => new Date(now.getTime() - h * 3_600_000).toISOString();
const fake = loadFakeData();

// Neutral incident: truck access, no skill-linked needs, no evacuation.
const baseIncident: Incident = {
  ...fake.incidents[0]!,
  id: 'INC-T',
  access_type: 'truck',
  needs: ['food_water'],
  people_count: 2,
  reporter_language: 'burmese',
};

// Neutral team: available, fresh, no skills, Thai only.
function team(id: string, over: Partial<Team> = {}): Team {
  return {
    ...fake.teams[0]!,
    id,
    name: id,
    status: 'available',
    vehicle: 'truck',
    skills: [],
    languages: ['thai'],
    carry_capacity: 10,
    on_duty_since: hoursAgo(1),
    last_check_in_at: hoursAgo(0.1),
    ...over,
  };
}

const travel = (minutes: Record<string, number>, incidentId = 'INC-T'): TravelTime[] =>
  Object.entries(minutes).map(([team_id, m]) => ({ team_id, incident_id: incidentId, minutes: m }));

function score(incident: Incident, t: Team, tt: TravelTime[] = []): number {
  const e = evaluateTeam(incident, t, tt, now);
  if (!e.eligible) throw new Error(`excluded: ${e.reasons.join('; ')}`);
  return e.score;
}

describe('rule: vehicle must fit access type', () => {
  it('excludes a truck from a boat-only incident and keeps boats', () => {
    const incident = { ...baseIncident, access_type: 'boat_only' as const };
    const e = evaluateTeam(incident, team('T'), [], now);
    expect(e).toMatchObject({ eligible: false, reasons: ['truck cannot reach boat only'] });
    expect(evaluateTeam(incident, team('B', { vehicle: 'flat_boat' }), [], now).eligible).toBe(true);
    expect(evaluateTeam(incident, team('K', { vehicle: 'kayak' }), [], now).eligible).toBe(true);
  });

  it('excludes boats from walk-only incidents', () => {
    const incident = { ...baseIncident, access_type: 'walk_only' as const };
    expect(evaluateTeam(incident, team('B', { vehicle: 'flat_boat' }), [], now).eligible).toBe(false);
    expect(evaluateTeam(incident, team('F', { vehicle: 'on_foot' }), [], now).eligible).toBe(true);
  });
});

describe('rule: capacity must fit people_count for evacuations', () => {
  const evac = { ...baseIncident, needs: ['evacuation' as const], people_count: 8 };

  it('excludes a team that cannot carry everyone', () => {
    const e = evaluateTeam(evac, team('small', { carry_capacity: 6 }), [], now);
    expect(e).toMatchObject({ eligible: false, reasons: ['carries 6, needs 8 evacuated'] });
  });

  it('accepts exactly enough capacity', () => {
    expect(evaluateTeam(evac, team('exact', { carry_capacity: 8 }), [], now).eligible).toBe(true);
  });

  it('ignores capacity when the incident is not an evacuation', () => {
    const food = { ...baseIncident, people_count: 8 };
    expect(evaluateTeam(food, team('small', { carry_capacity: 2 }), [], now).eligible).toBe(true);
  });
});

describe('rule: skill match is a big bonus', () => {
  const medical = { ...baseIncident, needs: ['medical' as const] };

  it('adds the bonus for first aid on a medical incident', () => {
    const withSkill = score(medical, team('A', { skills: ['first_aid'] }));
    const without = score(medical, team('B'));
    expect(withSkill - without).toBe(SKILL_MATCH_BONUS);
  });

  it('explains both a match and a gap', () => {
    expect(evaluateTeam(medical, team('A', { skills: ['first_aid'] }), [], now).reasons).toContain('Has first aid');
    expect(evaluateTeam(medical, team('B'), [], now).reasons).toContain('No first aid');
  });

  it('outweighs a moderate travel-time advantage', () => {
    const tt = travel({ near: 10, medic: 60 });
    const [best] = suggestTeams(medical, [team('near'), team('medic', { skills: ['first_aid'] })], tt, now);
    expect(best!.team.id).toBe('medic');
  });

  it('counts rescue → swimmer', () => {
    const rescue = { ...baseIncident, needs: ['rescue' as const] };
    expect(score(rescue, team('S', { skills: ['swimmer'] })) - score(rescue, team('N'))).toBe(SKILL_MATCH_BONUS);
  });
});

describe('rule: shorter travel time scores higher', () => {
  it('ranks the closer of two otherwise equal teams first', () => {
    const tt = travel({ far: 90, near: 15 });
    const ranked = suggestTeams(baseIncident, [team('far'), team('near')], tt, now);
    expect(ranked.map((s) => s.team.id)).toEqual(['near', 'far']);
    expect(ranked[0]!.reasons).toContain('About 15 min away');
  });

  it('gives full points at 0 min and none at or beyond the limit', () => {
    expect(score(baseIncident, team('A'), travel({ A: 0 }))).toBe(TRAVEL_MAX_POINTS);
    expect(score(baseIncident, team('A'), travel({ A: TRAVEL_ZERO_AT_MINUTES }))).toBe(0);
    expect(score(baseIncident, team('A'), travel({ A: TRAVEL_ZERO_AT_MINUTES * 3 }))).toBe(0);
  });

  it('treats a missing travel time as no travel points and says so', () => {
    const e = evaluateTeam(baseIncident, team('A'), [], now);
    expect(e).toMatchObject({ eligible: true, score: 0, reasons: ['Travel time unknown'] });
  });
});

describe('rule: fatigue lowers the score and excludes above the max', () => {
  it('does not penalise up to the free hours', () => {
    expect(score(baseIncident, team('A', { on_duty_since: hoursAgo(FATIGUE_FREE_HOURS) }))).toBe(0);
  });

  it('subtracts points for each hour beyond the free hours', () => {
    const s = score(baseIncident, team('A', { on_duty_since: hoursAgo(FATIGUE_FREE_HOURS + 3) }));
    expect(s).toBe(-3 * FATIGUE_PENALTY_PER_HOUR);
  });

  it('prefers a rested team over a tired one at the same distance', () => {
    const tt = travel({ tired: 20, rested: 20 });
    const teams = [team('tired', { on_duty_since: hoursAgo(14) }), team('rested', { on_duty_since: hoursAgo(2) })];
    expect(suggestTeams(baseIncident, teams, tt, now)[0]!.team.id).toBe('rested');
  });

  it(`excludes teams on duty more than ${MAX_HOURS_ON_DUTY} hours`, () => {
    const e = evaluateTeam(baseIncident, team('A', { on_duty_since: hoursAgo(MAX_HOURS_ON_DUTY + 0.5) }), [], now);
    expect(e).toMatchObject({ eligible: false, reasons: [`on duty ${MAX_HOURS_ON_DUTY} h (max ${MAX_HOURS_ON_DUTY} h)`] });
    expect(evaluateTeam(baseIncident, team('B', { on_duty_since: hoursAgo(MAX_HOURS_ON_DUTY) }), [], now).eligible).toBe(true);
  });
});

describe('rule: language match is a bonus', () => {
  it('adds the bonus when the team speaks the reporter language', () => {
    const s = score(baseIncident, team('A', { languages: ['thai', 'burmese'] }));
    expect(s).toBe(LANGUAGE_BONUS);
    expect(evaluateTeam(baseIncident, team('A', { languages: ['burmese'] }), [], now).reasons).toContain('Speaks burmese');
  });
});

describe('availability', () => {
  it('excludes teams that are busy, resting or off duty', () => {
    for (const status of ['en_route', 'on_scene', 'returning', 'resting', 'off_duty'] as const) {
      expect(evaluateTeam(baseIncident, team('A', { status }), [], now).eligible, status).toBe(false);
    }
  });
});

describe('suggestTeams', () => {
  it('returns at most the top 3, best first, with scores and reasons', () => {
    const teams = ['a', 'b', 'c', 'd'].map((id) => team(id));
    const tt = travel({ a: 40, b: 10, c: 30, d: 20 });
    const top = suggestTeams(baseIncident, teams, tt, now);
    expect(top.map((s) => s.team.id)).toEqual(['b', 'd', 'c']);
    expect(top[0]!.score).toBeGreaterThan(top[1]!.score);
    expect(top.every((s) => s.reasons.length > 0)).toBe(true);
  });

  it('returns an empty list when no team fits', () => {
    const incident = { ...baseIncident, access_type: 'boat_only' as const, needs: ['evacuation' as const], people_count: 20 };
    const teams = [
      team('truck'),
      team('small-boat', { vehicle: 'flat_boat', carry_capacity: 8 }),
      team('tired-boat', { vehicle: 'flat_boat', carry_capacity: 30, on_duty_since: hoursAgo(20) }),
      team('busy-boat', { vehicle: 'flat_boat', carry_capacity: 30, status: 'en_route' }),
    ];
    expect(suggestTeams(incident, teams, [], now)).toEqual([]);
    const all = evaluateTeams(incident, teams, [], now);
    expect(all.every((e) => !e.eligible && e.reasons.length > 0)).toBe(true);
  });

  it('never changes the teams (suggest only, no assignment)', () => {
    const teams = [team('a')];
    const before = JSON.stringify(teams);
    suggestTeams(baseIncident, teams, travel({ a: 5 }), now);
    expect(JSON.stringify(teams)).toBe(before);
  });

  it('suggests boats with a swimmer and first aid for the fake dialysis case', () => {
    const inc001 = fake.incidents.find((i) => i.id === 'INC-001')!;
    const at = new Date('2026-10-02T08:30:00+07:00');
    const top = suggestTeams(inc001, fake.teams, fake.travelTimes, at);
    expect(top.length).toBeGreaterThan(0);
    expect(top.every((s) => ['flat_boat', 'kayak'].includes(s.team.vehicle))).toBe(true);
  });

  it('does not let a skill bonus beat a much closer team (fake dialysis case)', () => {
    const inc001 = fake.incidents.find((i) => i.id === 'INC-001')!;
    const at = new Date('2026-10-02T08:30:00+07:00');
    const [best] = suggestTeams(inc001, fake.teams, fake.travelTimes, at);
    // Flat Boat 2 is ~21 min away without first aid; Flat Boat 1 has first aid but is ~5 h away.
    expect(best!.team.id).toBe('TEAM-03');
  });
});
