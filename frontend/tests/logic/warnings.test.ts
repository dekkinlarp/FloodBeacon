import { describe, expect, it } from 'vitest';
import type { Incident } from '../../src/types';
import { isOverdueCritical } from '../../src/logic/warnings';
import { loadFakeData } from '../../src/data/fakeData';

const now = new Date('2026-10-02T12:00:00+07:00');
const base = loadFakeData().incidents[0]!;
const inc = (over: Partial<Incident>): Incident => ({ ...base, severity: 'critical', status: 'verified', ...over });

describe('isOverdueCritical', () => {
  it('flags critical incidents without a team after more than 30 minutes', () => {
    expect(isOverdueCritical(inc({ created_at: '2026-10-02T11:29:00+07:00' }), now)).toBe(true);
    expect(isOverdueCritical(inc({ status: 'new', created_at: '2026-10-02T09:00:00+07:00' }), now)).toBe(true);
    expect(isOverdueCritical(inc({ status: 'could_not_reach', created_at: '2026-10-02T09:00:00+07:00' }), now)).toBe(true);
  });

  it('does not flag at exactly 30 minutes', () => {
    expect(isOverdueCritical(inc({ created_at: '2026-10-02T11:30:00+07:00' }), now)).toBe(false);
  });

  it('does not flag non-critical, assigned or closed incidents', () => {
    const old = '2026-10-02T08:00:00+07:00';
    expect(isOverdueCritical(inc({ severity: 'high', created_at: old }), now)).toBe(false);
    for (const status of ['assigned', 'en_route', 'on_scene', 'resolved', 'cancelled'] as const) {
      expect(isOverdueCritical(inc({ status, created_at: old }), now), status).toBe(false);
    }
  });
});
