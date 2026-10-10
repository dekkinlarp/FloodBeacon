import type { Health } from '../types';

interface Props {
  health: Health | undefined;
  onConfirm: () => void;
}

const words = (s: string) => s.replace(/_/g, ' ');

/**
 * Full health details. Shown only inside the incident detail panel, never on
 * the map or in logs (CLAUDE.md rule 7).
 */
export function HealthTriage({ health, onConfirm }: Props) {
  if (!health) {
    return (
      <section className="section">
        <h3 className="section__title">Health</h3>
        <p className="empty">No health record.</p>
      </section>
    );
  }
  const v = health.vulnerable;
  const vulnerable = (
    [
      ['elderly', v.elderly],
      ['children', v.children],
      ['pregnant', v.pregnant],
      ['disabled', v.disabled],
    ] as const
  ).filter(([, n]) => n > 0);

  return (
    <section className="section">
      <h3 className="section__title">
        Health <span className={`sev sev--${health.priority}`}>{health.priority}</span>
      </h3>
      {!health.verified_by_human && (
        <div className="flag flag--warn flag--row">
          <span>{health.ai_extracted ? 'AI-extracted, not yet confirmed' : 'Not yet confirmed'}</span>
          <button type="button" className="btn btn--small btn--primary" onClick={onConfirm}>
            Confirm
          </button>
        </div>
      )}
      <dl className="kv">
        <dt>Vulnerable</dt>
        <dd>{vulnerable.length ? vulnerable.map(([g, n]) => `${n} ${g}`).join(', ') : '—'}</dd>
        <dt>Injuries</dt>
        <dd>{health.injuries.length ? health.injuries.join('; ') : '—'}</dd>
        <dt>Mobility</dt>
        <dd>{health.mobility}</dd>
        <dt>Dependencies</dt>
        <dd>{health.medical_needs.map(words).join(', ') || '—'}</dd>
        <dt>Supplies left</dt>
        <dd>{health.supplies_left ?? 'unknown'}</dd>
        <dt>Notes</dt>
        <dd>{health.notes}</dd>
        <dt>Confirmed</dt>
        <dd>{health.verified_by_human ? 'yes, by dispatcher' : 'no'}</dd>
      </dl>
    </section>
  );
}
