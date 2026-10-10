import { describe, expect, it } from 'vitest';
import { initialDispatchState } from '../../src/logic/dispatch';
import type { DispatchState } from '../../src/logic/dispatch';
import { demoScore } from '../../src/logic/score';
import { loadFakeData } from '../../src/data/fakeData';
import type { Event } from '../../src/types';

const base = initialDispatchState(loadFakeData());

const onScene = (id: string, at: string): Event => ({
  id: `E-${id}-${at}`,
  occurred_at: at,
  actor: 'x',
  entity_type: 'incident',
  entity_id: id,
  event_type: 'status_changed',
  from_value: 'en_route',
  to_value: 'on_scene',
  note: null,
});

describe('demoScore', () => {
  it('is zero with no activity (fake data has one resting team)', () => {
    expect(demoScore(base)).toEqual({ resolved: 0, avgResponseMinutes: null, peopleReached: 0, teamsResting: 1 });
  });

  it('averages report → first on-scene time and ignores later on-scene events', () => {
    const s: DispatchState = {
      ...base,
      incidents: base.incidents.map((i) =>
        i.id === 'INC-001'
          ? { ...i, created_at: '2026-10-02T05:00:00+07:00', status: 'resolved' as const }
          : i.id === 'INC-002'
            ? { ...i, created_at: '2026-10-02T06:00:00+07:00' }
            : i,
      ),
      events: [
        onScene('INC-001', '2026-10-02T06:00:00+07:00'), // 60 min
        onScene('INC-001', '2026-10-02T09:00:00+07:00'), // later, ignored
        onScene('INC-002', '2026-10-02T07:30:00+07:00'), // 90 min
      ],
      feedback: [
        { id: 'F1', incident_id: 'INC-001', team_id: 'TEAM-02', submitted_at: '', submitted_by: '', water_depth_cm: null, route_worked: true, blocked_routes: '', people_helped: 3, outcome: 'evacuated', photo_ref: null },
        { id: 'F2', incident_id: 'INC-002', team_id: 'TEAM-03', submitted_at: '', submitted_by: '', water_depth_cm: null, route_worked: true, blocked_routes: '', people_helped: 4, outcome: 'supplied', photo_ref: null },
      ],
    };
    expect(demoScore(s)).toEqual({ resolved: 1, avgResponseMinutes: 75, peopleReached: 7, teamsResting: 1 });
  });
});
