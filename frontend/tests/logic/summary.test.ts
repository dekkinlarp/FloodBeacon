import { describe, expect, it } from 'vitest';
import { boardSummary } from '../../src/logic/summary';
import { loadFakeData } from '../../src/data/fakeData';

describe('boardSummary', () => {
  it('counts open, critical, waiting and overdue incidents and team availability', () => {
    const { incidents, teams } = loadFakeData();
    // 20 incidents, 1 cancelled; 3 critical; all others new/verified; teams: 4 available, 1 resting, 1 off duty
    const now = new Date('2026-10-02T09:00:00+07:00');
    expect(boardSummary(incidents, teams, now)).toEqual({
      open: 19,
      critical: 3,
      waiting: 19,
      overdueCritical: 3,
      teamsAvailable: 4,
      teamsOnDuty: 5,
    });
  });

  it('does not count resolved incidents as open', () => {
    const { incidents, teams } = loadFakeData();
    const resolved = incidents.map((i) => (i.id === 'INC-001' ? { ...i, status: 'resolved' as const } : i));
    const s = boardSummary(resolved, teams, new Date('2026-10-02T09:00:00+07:00'));
    expect([s.open, s.critical, s.overdueCritical]).toEqual([18, 2, 2]);
  });
});
