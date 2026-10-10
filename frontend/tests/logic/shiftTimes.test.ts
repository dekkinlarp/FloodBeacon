import { describe, expect, it } from 'vitest';
import { latestTimestamp, offsetToNow, shiftRecords } from '../../src/logic/shiftTimes';
import { loadFakeData } from '../../src/data/fakeData';

describe('shiftTimes', () => {
  const records = [
    { id: 'a', t: '2026-10-02T05:00:00+07:00', u: null as string | null },
    { id: 'b', t: '2026-10-02T06:30:00+07:00', u: '2026-10-02T07:00:00+07:00' },
  ];

  it('finds the latest timestamp across fields and skips nulls', () => {
    expect(latestTimestamp([{ records, fields: ['t', 'u'] }])).toBe(Date.parse('2026-10-02T07:00:00+07:00'));
    expect(latestTimestamp([{ records: [], fields: ['t'] }])).toBeNull();
  });

  it('shifts listed fields by the offset, keeps nulls, and does not mutate input', () => {
    const out = shiftRecords(records, ['t', 'u'], 60 * 60 * 1000);
    expect(out[0]).toEqual({ id: 'a', t: '2026-10-01T23:00:00.000Z', u: null });
    expect(out[1]!.u).toBe('2026-10-02T01:00:00.000Z');
    expect(records[0]!.t).toBe('2026-10-02T05:00:00+07:00');
  });

  it('computes the offset that puts the latest time just before now', () => {
    const now = new Date('2026-10-03T12:00:00Z');
    expect(offsetToNow(now.getTime() - 10_000, now, 5_000)).toBe(5_000);
  });
});

describe('loadFakeData shiftTo', () => {
  it('moves the newest fake timestamp to 5 minutes before the given time and keeps gaps', () => {
    const at = new Date('2026-10-03T16:00:00+07:00');
    const raw = loadFakeData();
    const shifted = loadFakeData({ shiftTo: at });
    const newest = Math.max(
      ...shifted.incidents.flatMap((i) => [i.created_at, i.updated_at, i.last_contact_at].filter((x) => x !== null).map((x) => Date.parse(x!))),
      ...shifted.health.map((h) => Date.parse(h.updated_at)),
      ...shifted.teams.flatMap((t) => [t.on_duty_since, t.last_check_in_at].filter((x) => x !== null).map((x) => Date.parse(x!))),
    );
    expect(newest).toBe(at.getTime() - 5 * 60_000);
    const gap = (d: typeof raw) => Date.parse(d.incidents[1]!.created_at) - Date.parse(d.incidents[0]!.created_at);
    expect(gap(shifted)).toBe(gap(raw));
    expect(shifted.teams.find((t) => t.id === 'TEAM-06')!.on_duty_since).toBeNull();
  });
});
