import { describe, expect, it } from 'vitest';
import { isValidActor, parseAction, runAction } from '../../src/logic/actions';
import { initialDispatchState } from '../../src/logic/dispatch';
import { loadFakeData } from '../../src/data/fakeData';

const ctx = { now: new Date('2026-10-02T08:30:00+07:00'), actor: 'dispatcher' };

describe('runAction', () => {
  it('runs an action through the same rules as the UI', () => {
    const r = runAction(initialDispatchState(loadFakeData()), { type: 'assign', incidentId: 'INC-001', teamId: 'TEAM-02', backup: false }, ctx);
    expect(r.ok && r.state.incidents.find((i) => i.id === 'INC-001')!.status).toBe('assigned');
  });

  it('returns the rule refusal unchanged', () => {
    const r = runAction(initialDispatchState(loadFakeData()), { type: 'assign', incidentId: 'INC-001', teamId: 'TEAM-01', backup: false }, ctx);
    expect(r).toEqual({ ok: false, reasons: ['Truck 1 (truck) cannot reach boat only incidents.'] });
  });
});

describe('parseAction', () => {
  it('accepts well-formed actions', () => {
    expect(parseAction({ type: 'recall', teamId: 'TEAM-02' })).toEqual({ type: 'recall', teamId: 'TEAM-02' });
    expect(parseAction({ type: 'incidentStatus', incidentId: 'INC-1', to: 'verified', extra: 1 })).toEqual({
      type: 'incidentStatus',
      incidentId: 'INC-1',
      to: 'verified',
    });
  });

  it('rejects unknown types, missing fields and bad statuses', () => {
    expect(parseAction({ type: 'dropTables' })).toBeNull();
    expect(parseAction({ type: 'assign', incidentId: 'INC-1', teamId: 'T' })).toBeNull();
    expect(parseAction({ type: 'incidentStatus', incidentId: 'INC-1', to: 'done' })).toBeNull();
    expect(parseAction({ type: 'recall', teamId: 'x'.repeat(101) })).toBeNull();
    expect(parseAction(null)).toBeNull();
    expect(parseAction({ type: 'feedback', input: { teamId: 'T', route_worked: 'yes' } })).toBeNull();
  });
});

describe('isValidActor', () => {
  it('accepts the dispatcher and team actors only', () => {
    expect(isValidActor('dispatcher')).toBe(true);
    expect(isValidActor('team:TEAM-02')).toBe(true);
    expect(isValidActor('admin')).toBe(false);
    expect(isValidActor('team:<script>')).toBe(false);
    expect(isValidActor(undefined)).toBe(false);
  });
});
