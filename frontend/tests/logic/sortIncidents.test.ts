import { describe, expect, it } from 'vitest';
import type { Incident } from '../../src/types';
import { sortIncidents } from '../../src/logic/sortIncidents';
import { loadFakeData } from '../../src/data/fakeData';

// 10 minutes after the latest created_at below, so nothing is an overdue critical.
const now = new Date('2026-10-02T09:10:00+07:00');

function inc(
  id: string,
  severity: Incident['severity'],
  created_at: string,
  status: Incident['status'] = 'verified',
): Incident {
  return { ...loadFakeData().incidents[0]!, id, severity, created_at, status };
}

describe('sortIncidents', () => {
  it('puts higher severity first', () => {
    const sorted = sortIncidents([
      inc('A', 'low', '2026-10-02T01:00:00+07:00'),
      inc('B', 'critical', '2026-10-02T09:00:00+07:00'),
      inc('C', 'medium', '2026-10-02T02:00:00+07:00'),
      inc('D', 'high', '2026-10-02T03:00:00+07:00'),
    ], now);
    expect(sorted.map((i) => i.id)).toEqual(['B', 'D', 'C', 'A']);
  });

  it('puts the longest waiting first within a severity, comparing across time zones', () => {
    const sorted = sortIncidents([
      inc('late', 'high', '2026-10-02T08:00:00+07:00'),
      inc('early-utc', 'high', '2026-10-02T00:30:00Z'), // 07:30 Bangkok
      inc('earliest', 'high', '2026-10-02T06:00:00+07:00'),
    ], now);
    expect(sorted.map((i) => i.id)).toEqual(['earliest', 'early-utc', 'late']);
  });

  it('breaks exact ties by id and does not mutate the input', () => {
    const input = [inc('B', 'low', '2026-10-02T06:00:00+07:00'), inc('A', 'low', '2026-10-02T06:00:00+07:00')];
    expect(sortIncidents(input, now).map((i) => i.id)).toEqual(['A', 'B']);
    expect(input.map((i) => i.id)).toEqual(['B', 'A']);
  });

  it('starts the fake data with the two critical cases', () => {
    const top = sortIncidents(loadFakeData().incidents, now).slice(0, 3);
    expect(top.every((i) => i.severity === 'critical')).toBe(true);
    expect(top.map((i) => i.id)).toEqual(['INC-001', 'INC-002', 'INC-009']);
  });

  it('moves critical incidents unassigned for more than 30 minutes to the very top', () => {
    const sorted = sortIncidents(
      [
        inc('critical-old-assigned', 'critical', '2026-10-02T07:00:00+07:00', 'assigned'),
        inc('critical-fresh', 'critical', '2026-10-02T09:00:00+07:00'),
        inc('critical-overdue', 'critical', '2026-10-02T08:30:00+07:00', 'new'),
      ],
      now,
    );
    expect(sorted.map((i) => i.id)).toEqual(['critical-overdue', 'critical-old-assigned', 'critical-fresh']);
  });
});
