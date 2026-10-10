import type { DemoLogEntry, DemoScript } from '../logic/demo';
import { DEMO_SPEED, formatElapsed } from '../logic/clock';
import { demoScore } from '../logic/score';
import type { DispatchState } from '../logic/dispatch';
import { useClock } from '../state/Clock';

const SPEEDS = [
  { label: '1h = 10s', value: DEMO_SPEED },
  { label: '1h = 1m', value: 60 },
  { label: 'real time', value: 1 },
];

interface Props {
  script: DemoScript;
  data: DispatchState;
  demoLog: readonly DemoLogEntry[];
  demoDone: ReadonlySet<string>;
  now: Date;
  /** Start demo mode: fresh data with T+0 at `simStart`. */
  onStartDemo: (simStart: Date) => void;
  onReset: () => void;
  onExit: () => void;
}

/** Demo controls for the header. In live mode, only the start button. */
export function DemoBar({ script, data, demoLog, demoDone, now, onStartDemo, onReset, onExit }: Props) {
  const clock = useClock();
  const c = clock.clock;

  if (!c) {
    return (
      <button
        type="button"
        className="btn btn--ghost"
        title={script.title}
        onClick={() => onStartDemo(new Date(Math.floor(Date.now() / 60_000) * 60_000))}
      >
        ▶ Demo
      </button>
    );
  }

  // `now` is already simulated time.
  const elapsed = (now.getTime() - c.simStart) / 60_000;
  const next = script.steps.find((s) => !demoDone.has(s.id));
  const last = demoLog.at(-1);
  const score = demoScore(data);

  return (
    <div className="demo">
      <div className="demo__controls">
        <span className="demo__elapsed">{formatElapsed(elapsed)}</span>
        {c.running ? (
          <button type="button" className="btn btn--small" onClick={clock.pause}>
            Pause
          </button>
        ) : (
          <button type="button" className="btn btn--small btn--primary" onClick={clock.play}>
            {elapsed === 0 ? 'Start' : 'Resume'}
          </button>
        )}
        <select aria-label="Demo speed" value={c.speed} onChange={(e) => clock.setSpeed(Number(e.target.value))}>
          {SPEEDS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
        <button type="button" className="btn btn--small" onClick={onReset}>
          Reset demo
        </button>
        <button type="button" className="btn btn--small btn--ghost" onClick={onExit}>
          Exit
        </button>
      </div>
      <div className="demo__story" title={demoLog.map((e) => `${e.stepId} ${e.kind}: ${e.message}`).join('\n')}>
        {last && <span className={`demo__last demo__last--${last.kind}`}>{last.message}</span>}
        <span className="demo__next">{next ? `Next ${formatElapsed(next.at_minutes)} · ${next.label}` : 'Story complete'}</span>
      </div>
      <dl className="demo__score" aria-label="Demo score">
        <div>
          <dt>Resolved</dt>
          <dd>{score.resolved}</dd>
        </div>
        <div>
          <dt>Avg resp</dt>
          <dd>{score.avgResponseMinutes === null ? '–' : `${Math.round(score.avgResponseMinutes)}m`}</dd>
        </div>
        <div>
          <dt>Reached</dt>
          <dd>{score.peopleReached}</dd>
        </div>
        <div>
          <dt>Resting</dt>
          <dd>{score.teamsResting}</dd>
        </div>
      </dl>
    </div>
  );
}
