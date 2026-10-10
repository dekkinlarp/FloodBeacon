import { describe, expect, it } from 'vitest';
import type { DispatchState } from '../../src/logic/dispatch';
import { assignTeam, initialDispatchState, updateIncidentStatus } from '../../src/logic/dispatch';
import type { DemoScript } from '../../src/logic/demo';
import { DEMO_DISPATCHER, applyDemoStep, dueSteps, runDueSteps, validateDemoScript } from '../../src/logic/demo';
import { demoScore } from '../../src/logic/score';
import { loadFakeData } from '../../src/data/fakeData';
import { loadDemoScript } from '../../src/data/demoScript';
import { validateDataset } from '../../src/logic/validateData';

const T0 = Date.parse('2026-10-03T09:00:00+07:00');
const min = (m: number) => T0 + m * 60_000;
const script = loadDemoScript();

function startState(): DispatchState {
  return initialDispatchState(loadFakeData({ shiftTo: new Date(T0) }));
}

const inc = (s: DispatchState, id: string) => s.incidents.find((i) => i.id === id);

describe('demo script file', () => {
  it('is valid and tells the story in order', () => {
    expect(validateDemoScript(script)).toEqual([]);
    expect(script.steps.map((s) => [s.at_minutes, s.type])).toEqual([
      [0, 'note'],
      [60, 'incident_reported'],
      [85, 'verify_incident'],
      [90, 'assign_suggested'],
      [95, 'field_report'],
      [120, 'route_change'],
      [180, 'field_report'],
      [210, 'feedback'],
    ]);
  });

  it('reports a critical, boat-only dialysis case in Bang Kapi', () => {
    const step = script.steps.find((s) => s.type === 'incident_reported');
    expect(step?.type === 'incident_reported' && step.incident).toMatchObject({
      district: 'Bang Kapi',
      severity: 'critical',
      access_type: 'boat_only',
      ai_extracted: true,
      verified_by_human: false,
    });
    expect(step?.type === 'incident_reported' && step.health?.medical_needs).toContain('dialysis');
  });

  it('rejects broken scripts', () => {
    expect(validateDemoScript({ version: 1, steps: [{ id: 'a', at_minutes: 5, label: '', type: 'note' }, { id: 'a', at_minutes: 1, label: '', type: 'warp' }] }))
      .toEqual(['steps[1].id: duplicate a', 'steps[1].at_minutes: steps must be in time order', 'steps[1].type: unknown warp']);
    expect(validateDemoScript(null)).toEqual(['script: expected object']);
  });
});

describe('dueSteps', () => {
  it('returns steps whose time has come and that have not run', () => {
    expect(dueSteps(script, new Set(), 59).map((s) => s.id)).toEqual(['S1']);
    expect(dueSteps(script, new Set(['S1']), 90).map((s) => s.id)).toEqual(['S2', 'S3', 'S4']);
  });
});

describe('the whole story plays end to end', () => {
  // Advance like the UI does: small clock ticks, running due steps each time.
  function play(until: number, tickMinutes = 1.5) {
    let state = startState();
    const done = new Set<string>();
    const log = [];
    for (let m = 0; m <= until; m += tickMinutes) {
      const r = runDueSteps(state, script, done, T0, min(m));
      state = r.state;
      for (const e of r.log) {
        done.add(e.stepId);
        log.push(e);
      }
    }
    return { state, log };
  }

  it('applies every step without a failure', () => {
    const { log } = play(240);
    expect(log.map((e) => [e.stepId, e.kind])).toEqual([
      ['S1', 'skipped'], // note only
      ['S2', 'applied'],
      ['S3', 'applied'],
      ['S4', 'applied'],
      ['S5', 'applied'],
      ['S6', 'applied'],
      ['S7', 'applied'],
      ['S8', 'applied'],
    ]);
  });

  it('assigns the suggested boat team, re-routes truck → boat with an alert, and resolves', () => {
    const { state, log } = play(240);
    const assignment = state.assignments.find((a) => a.incident_id === 'INC-021')!;
    const team = state.teams.find((t) => t.id === assignment.team_id)!;
    expect(['flat_boat', 'kayak']).toContain(team.vehicle);
    expect(team.id).toBe('TEAM-02'); // nearest boat that can carry 2 people
    expect(log.find((e) => e.stepId === 'S4')!.message).toMatch(/top suggestion/);

    expect(state.routePlans).toEqual([
      expect.objectContaining({ incident_id: 'INC-021', team_id: 'TEAM-02', legs: [{ mode: 'truck', minutes: 25 }, { mode: 'boat', minutes: 30 }] }),
    ]);
    expect(state.alerts).toHaveLength(1);
    expect(state.alerts[0]!.message).toContain('Now truck 25 min → boat 30 min');

    expect(inc(state, 'INC-021')!.status).toBe('resolved');
    expect(team.status).toBe('returning');
    expect(state.feedback).toEqual([expect.objectContaining({ outcome: 'evacuated', people_helped: 2, team_id: 'TEAM-02' })]);
  });

  it('writes events at the scripted simulated times, with no health values', () => {
    const { state } = play(240);
    const at = (pred: (e: (typeof state.events)[number]) => boolean) => state.events.find(pred)?.occurred_at;
    expect(at((e) => e.entity_type === 'incident' && e.event_type === 'created')).toBe(new Date(min(60)).toISOString());
    expect(at((e) => e.to_value === 'on_scene' && e.entity_type === 'incident')).toBe(new Date(min(180)).toISOString());
    expect(JSON.stringify(state.events)).not.toMatch(/hemodialysis|Chest-deep/i);
  });

  it('scores the run', () => {
    const { state } = play(240);
    expect(demoScore(state)).toEqual({ resolved: 1, avgResponseMinutes: 120, peopleReached: 2, teamsResting: 1 });
  });

  it('gives the same result when the clock jumps straight to the end', () => {
    const r = runDueSteps(startState(), script, new Set(), T0, min(500));
    expect(r.log.filter((e) => e.kind === 'failed')).toEqual([]);
    expect(inc(r.state, 'INC-021')!.status).toBe('resolved');
    expect(r.log.find((e) => e.stepId === 'S7')!.at).toBe(new Date(min(180)).toISOString());
  });

  it('keeps the rest of the fake data valid', () => {
    const { state } = play(240);
    expect(validateDataset({ incidents: state.incidents, health: state.health, teams: state.teams })).toEqual([]);
  });
});

describe('the dispatcher can still act manually', () => {
  it('skips scripted steps the dispatcher already did and continues the story', () => {
    let state = startState();
    const done = new Set<string>();
    const run = (m: number) => {
      const r = runDueSteps(state, script, done, T0, min(m));
      state = r.state;
      r.log.forEach((e) => done.add(e.stepId));
      return r.log;
    };
    run(60); // SMS arrives
    const ctx = { now: new Date(min(70)), actor: 'dispatcher' };
    state = (updateIncidentStatus(state, 'INC-021', 'verified', ctx) as { state: DispatchState }).state;
    const manual = assignTeam(state, 'INC-021', 'TEAM-02', ctx);
    if (!manual.ok) throw new Error(manual.reasons.join());
    state = manual.state;

    const log = run(240);
    expect(log.find((e) => e.stepId === 'S3')).toMatchObject({ kind: 'skipped', message: 'INC-021 is already assigned.' });
    expect(log.find((e) => e.stepId === 'S4')).toMatchObject({ kind: 'skipped', message: 'INC-021 already has TEAM-02.' });
    expect(log.filter((e) => e.kind === 'failed')).toEqual([]);
    expect(inc(state, 'INC-021')!.status).toBe('resolved');
    expect(state.events.filter((e) => e.actor === DEMO_DISPATCHER && e.event_type === 'assigned')).toEqual([]);
  });

  it('skips rather than fails when a step cannot happen', () => {
    const step = script.steps.find((s) => s.type === 'feedback')!;
    expect(applyDemoStep(startState(), step, new Date(min(210)))).toEqual({
      kind: 'skipped',
      message: 'INC-021 does not exist yet.',
    });
  });

  it('skips the assignment when no boat team is free', () => {
    const s = startState();
    const busy: DispatchState = { ...s, teams: s.teams.map((t) => ({ ...t, status: 'resting' as const })) };
    const reported = runDueSteps(busy, script, new Set(['S1']), T0, min(85)).state;
    const step = script.steps.find((x) => x.id === 'S4')!;
    expect(applyDemoStep(reported, step, new Date(min(90)))).toMatchObject({ kind: 'skipped' });
  });
});

describe('script type', () => {
  it('matches the DemoScript shape', () => {
    const typed: DemoScript = script;
    expect(typed.version).toBe(1);
  });
});
