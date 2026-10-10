import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { DemoClock } from '../logic/clock';
import { DEMO_SPEED, createClock, pause, reset, setSpeed, simNow, start } from '../logic/clock';

// The one place the app reads the time. Live mode: the real clock. Demo mode:
// the simulated clock from src/logic/clock.ts.

interface ClockApi {
  mode: 'live' | 'demo';
  clock: DemoClock | null;
  /** Current time: simulated in demo mode, real otherwise. */
  now: () => Date;
  /** Switch to demo mode with T+0 at `simStart` (paused). */
  enterDemo: (simStart: number) => void;
  exitDemo: () => void;
  play: () => void;
  pause: () => void;
  setSpeed: (speed: number) => void;
  /** Back to T+0, paused. */
  resetClock: () => void;
}

const ClockContext = createContext<ClockApi | null>(null);

export function ClockProvider({ children }: { children: ReactNode }) {
  const [clock, setClock] = useState<DemoClock | null>(null);
  const now = useCallback(() => new Date(clock ? simNow(clock, Date.now()) : Date.now()), [clock]);
  const api = useMemo<ClockApi>(
    () => ({
      mode: clock ? 'demo' : 'live',
      clock,
      now,
      enterDemo: (simStart) => setClock(createClock(simStart, Date.now(), DEMO_SPEED)),
      exitDemo: () => setClock(null),
      play: () => setClock((c) => (c ? start(c, Date.now()) : c)),
      pause: () => setClock((c) => (c ? pause(c, Date.now()) : c)),
      setSpeed: (speed) => setClock((c) => (c ? setSpeed(c, speed, Date.now()) : c)),
      resetClock: () => setClock((c) => (c ? reset(c, Date.now()) : c)),
    }),
    [clock, now],
  );
  return <ClockContext.Provider value={api}>{children}</ClockContext.Provider>;
}

export function useClock(): ClockApi {
  const api = useContext(ClockContext);
  if (!api) throw new Error('useClock must be used inside ClockProvider');
  return api;
}

/** Re-renders on a timer and returns the current (possibly simulated) time. */
export function useNow(): Date {
  const { now, clock } = useClock();
  const [, setTick] = useState(0);
  const fast = !!clock?.running;
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), fast ? 250 : 30_000);
    return () => clearInterval(id);
  }, [fast]);
  return now();
}
