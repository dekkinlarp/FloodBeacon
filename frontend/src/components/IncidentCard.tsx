import type { ReactNode } from 'react';
import type { Health, Incident } from '../types';
import { contactBadge } from '../logic/contactBadge';
import { emergencyReminders } from '../logic/emergencyReminder';
import { needLabel } from './NeedIcon';
import { HealthTriage } from './HealthTriage';

interface Props {
  incident: Incident;
  /** Full health details are shown only here, never on the map (CLAUDE.md rule 7). */
  health: Health | undefined;
  now: Date;
  onClose: () => void;
  onConfirmHealth: () => void;
  /** Dispatch controls, rendered after the key facts. */
  children?: ReactNode;
}

const words = (s: string) => s.replace(/_/g, ' ');

const timeFormat = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Bangkok',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});

function formatTime(iso: string | null): string {
  return iso ? timeFormat.format(new Date(iso)) : '—';
}

/** Detail panel for the selected incident. */
export function IncidentCard({ incident, health, now, onClose, onConfirmHealth, children }: Props) {
  const badge = contactBadge(incident, now);
  const reminders = emergencyReminders(incident, health);

  return (
    <aside className="detail" aria-labelledby="detail-title">
      <header className={`detail__header detail__header--${incident.severity}`}>
        <div>
          <h2 id="detail-title" className="detail__id">
            {incident.id}
          </h2>
          <p className="detail__where">{incident.district}</p>
        </div>
        <div className="detail__pills">
          <span className={`sev sev--${incident.severity}`}>{incident.severity}</span>
          <span className={`pill pill--${incident.status}`}>{words(incident.status)}</span>
        </div>
        <button type="button" className="detail__close" onClick={onClose} aria-label="Close">
          ×
        </button>
      </header>

      <div className="detail__body">
        {reminders.map((r) => (
          <p key={r.number} className="callout" role="alert">
            <span className="callout__number">CALL {r.number}</span>
            <span>{r.label.replace(/^Call \d+ — /, '')}</span>
          </p>
        ))}

        <dl className="facts">
          <div>
            <dt>Access</dt>
            <dd>{words(incident.access_type)}</dd>
          </div>
          <div>
            <dt>People</dt>
            <dd>{incident.people_count}</dd>
          </div>
          <div>
            <dt>Needs</dt>
            <dd>{incident.needs.map(needLabel).join(', ') || '—'}</dd>
          </div>
          <div>
            <dt>Last contact</dt>
            <dd className={badge.overdue ? 'text-danger' : undefined}>
              {badge.label} ago · {formatTime(incident.last_contact_at)}
            </dd>
          </div>
          <div className="facts__wide">
            <dt>Address</dt>
            <dd>{incident.address_note}</dd>
          </div>
        </dl>

        {children}

        <section className="section">
          <h3 className="section__title">
            Report
            <span className="section__meta">
              {incident.source} · {formatTime(incident.created_at)} · {incident.reporter_language}
              {incident.contact_phone && ` · ${incident.contact_phone}`}
            </span>
          </h3>
          {incident.ai_extracted && (
            <p className={incident.verified_by_human ? 'flag flag--ok' : 'flag flag--warn'}>
              AI-extracted · verified_by_human: <strong>{incident.verified_by_human ? 'yes' : 'NO — check before acting'}</strong>
            </p>
          )}
          {incident.original_message ? (
            <blockquote className="quote" lang={incident.reporter_language === 'thai' ? 'th' : undefined}>
              {incident.original_message}
            </blockquote>
          ) : (
            <p className="empty">No original message ({incident.source} report).</p>
          )}
        </section>

        <HealthTriage health={health} onConfirm={onConfirmHealth} />
      </div>
    </aside>
  );
}
