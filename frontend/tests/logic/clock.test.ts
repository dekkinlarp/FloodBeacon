import { describe, expect, it } from 'vitest';
import {
  DEMO_SPEED,
  createClock,
  elapsedMinutes,
  formatElapsed,
  pause,
  reset,
  setSpeed,
  simNow,
  start,
} from '../../src/logic/clock';

const T0 = Date.parse('2026-10-03T08:00:00+07:00');
const HOUR = 3_600_000;

describe('demo clock', () => {
  it('runs 1 simulated hour per 10 real seconds by default', () => {
    expect(DEMO_SPEED).toBe(360);
    const c = start(createClock(T0, 1_000), 1_000);
    expect(simNow(c, 11_000) - T0).toBe(HOUR);
    expect(elapsedMinutes(c, 16_000)).toBe(90);
  });

  it('starts paused and does not move until started', () => {
    const c = createClock(T0, 0);
    expect(c.running).toBe(false);
    expect(simNow(c, 999_999)).toBe(T0);
  });

  it('holds the time while paused and resumes from there', () => {
    let c = start(createClock(T0, 0), 0);
    c = pause(c, 5_000); // +30 min
    expect(simNow(c, 60_000)).toBe(T0 + HOUR / 2);
    c = start(c, 60_000);
    expect(simNow(c, 65_000)).toBe(T0 + HOUR); // another 30 min
  });

  it('changes speed without jumping', () => {
    let c = start(createClock(T0, 0), 0);
    c = setSpeed(c, 60, 10_000); // at T+1h
    expect(simNow(c, 10_000)).toBe(T0 + HOUR);
    expect(simNow(c, 70_000)).toBe(T0 + HOUR + HOUR); // 60 s × 60 = 1 h
    expect(() => setSpeed(c, 0, 0)).toThrow();
  });

  it('ignores real time going backwards', () => {
    const c = start(createClock(T0, 10_000), 10_000);
    expect(simNow(c, 5_000)).toBe(T0);
  });

  it('start and pause are idempotent', () => {
    const c = start(createClock(T0, 0), 0);
    expect(start(c, 5_000)).toBe(c);
    const p = pause(c, 1_000);
    expect(pause(p, 9_000)).toBe(p);
  });

  it('resets to T+0, paused, keeping the speed', () => {
    let c = setSpeed(start(createClock(T0, 0), 0), 120, 1_000);
    c = reset(c, 50_000);
    expect(c).toMatchObject({ running: false, speed: 120, simStart: T0 });
    expect(simNow(c, 90_000)).toBe(T0);
  });

  it('formats elapsed time', () => {
    expect(formatElapsed(0)).toBe('T+0h 00m');
    expect(formatElapsed(95.9)).toBe('T+1h 35m');
    expect(formatElapsed(-3)).toBe('T+0h 00m');
  });
});
