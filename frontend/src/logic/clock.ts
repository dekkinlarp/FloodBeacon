// Simulated clock for demo mode. Pure: every function takes the real time
// (ms) and returns a new clock or a simulated time. Nothing reads Date.now().

/** Default demo speed: 1 simulated hour per 10 real seconds. */
export const DEMO_SPEED = 360;

export interface DemoClock {
  /** Simulated time (ms) at `realAnchor`. */
  simAnchor: number;
  /** Real time (ms) when the clock was last started, paused or re-timed. */
  realAnchor: number;
  /** Simulated ms per real ms. */
  speed: number;
  running: boolean;
  /** Simulated time (ms) the demo started at (T+0). */
  simStart: number;
}

/** A paused clock at `simStart`. */
export function createClock(simStart: number, realNow: number, speed = DEMO_SPEED): DemoClock {
  if (!(speed > 0)) throw new Error('speed must be > 0');
  return { simAnchor: simStart, realAnchor: realNow, speed, running: false, simStart };
}

/** Simulated time (ms) at real time `realNow`. */
export function simNow(clock: DemoClock, realNow: number): number {
  if (!clock.running) return clock.simAnchor;
  return clock.simAnchor + Math.max(0, realNow - clock.realAnchor) * clock.speed;
}

/** Re-anchors at `realNow` so later changes don't jump the simulated time. */
function reanchor(clock: DemoClock, realNow: number): DemoClock {
  return { ...clock, simAnchor: simNow(clock, realNow), realAnchor: realNow };
}

export function start(clock: DemoClock, realNow: number): DemoClock {
  if (clock.running) return clock;
  return { ...clock, realAnchor: realNow, running: true };
}

export function pause(clock: DemoClock, realNow: number): DemoClock {
  if (!clock.running) return clock;
  return { ...reanchor(clock, realNow), running: false };
}

export function setSpeed(clock: DemoClock, speed: number, realNow: number): DemoClock {
  if (!(speed > 0)) throw new Error('speed must be > 0');
  return { ...reanchor(clock, realNow), speed };
}

/** Back to T+0, paused. */
export function reset(clock: DemoClock, realNow: number): DemoClock {
  return createClock(clock.simStart, realNow, clock.speed);
}

/** Simulated minutes since T+0. */
export function elapsedMinutes(clock: DemoClock, realNow: number): number {
  return (simNow(clock, realNow) - clock.simStart) / 60_000;
}

/** "T+1h 30m" style label for a number of simulated minutes. */
export function formatElapsed(minutes: number): string {
  const m = Math.max(0, Math.floor(minutes));
  return `T+${Math.floor(m / 60)}h ${String(m % 60).padStart(2, '0')}m`;
}
