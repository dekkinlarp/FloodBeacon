import type { Incident } from '../types';
import { formatHours, hoursSince } from '../logic/contactBadge';
import { mainNeed } from '../logic/mainNeed';
import { CRITICAL_UNASSIGNED_MINUTES, isOverdueCritical } from '../logic/warnings';
import { NeedIcon, needLabel } from './NeedIcon';
import { PanelToggle } from './PanelToggle';

interface Props {
  /** Already sorted by the caller. */
  incidents: readonly Incident[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  now: Date;
  /** Desktop only: the queue folds into a narrow rail (see .dispatch--queue-collapsed). */
  collapsed: boolean;
  onToggleCollapsed: () => void;
}

const words = (s: string) => s.replace(/_/g, ' ');

/**
 * Incident queue. Each row carries a segmented meter that fills toward the 30-minute
 * no-team limit; overdue critical cases also get a red row tint and a "No team" tag.
 */
export function IncidentList({ incidents, selectedId, onSelect, now, collapsed, onToggleCollapsed }: Props) {
  const open = incidents.filter((i) => i.status !== 'resolved' && i.status !== 'cancelled').length;
  const overdueCount = incidents.filter((i) => isOverdueCritical(i, now)).length;
  return (
    <nav className="queue" aria-label="Incident queue">
      <h2 className="panel-title">
        Queue <span className="panel-title__count">{open} open</span>
        <span className="panel-title__actions">
          <PanelToggle label="queue" expanded={!collapsed} controls="queue-list" toward="left" onToggle={onToggleCollapsed} />
        </span>
      </h2>
      <button type="button" className="queue__rail" aria-label={`Expand queue, ${open} open`} onClick={onToggleCollapsed}>
        <span className="queue__rail-chevron" aria-hidden="true">
          <svg width="14" height="14" viewBox="0 0 14 14">
            <path d="M5.5 3.5 9 7l-3.5 3.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
        <span className="queue__rail-label">Queue</span>
        <span className="panel-title__count">{open}</span>
        {overdueCount > 0 && (
          <span className="queue__rail-overdue" title={`${overdueCount} critical with no team for over 30 minutes`}>
            {overdueCount}
          </span>
        )}
      </button>
      <ol className="queue__list" id="queue-list">
        {incidents.map((incident) => {
          const overdue = isOverdueCritical(incident, now);
          const need = mainNeed(incident);
          const closed = incident.status === 'resolved' || incident.status === 'cancelled';
          const waited = hoursSince(incident.created_at, now);
          const level = closed ? 0 : Math.min(1, (waited * 60) / CRITICAL_UNASSIGNED_MINUTES);
          const cls = [
            'qrow',
            `qrow--${incident.severity}`,
            incident.id === selectedId && 'qrow--selected',
            overdue && 'qrow--overdue',
            closed && 'qrow--closed',
          ]
            .filter(Boolean)
            .join(' ');
          return (
            <li key={incident.id}>
              <button
                type="button"
                className={cls}
                aria-current={incident.id === selectedId}
                onClick={() => onSelect(incident.id)}
              >
                <span className="qrow__line">
                  <span className="qrow__district">{incident.district}</span>
                  <span
                    className="meter"
                    role="meter"
                    aria-label={`Wait toward the ${CRITICAL_UNASSIGNED_MINUTES}-minute no-team limit`}
                    aria-valuemin={0}
                    aria-valuemax={1}
                    aria-valuenow={Math.round(level * 100) / 100}
                  >
                    <span style={{ width: `${level * 100}%` }} />
                  </span>
                  <span className="qrow__wait" title="Waiting since report">
                    {formatHours(waited)}
                  </span>
                </span>
                <span className="qrow__line qrow__meta">
                  <span className="qrow__sev" aria-hidden="true" />
                  <span className="qrow__need">
                    <NeedIcon need={need} size={12} />
                    {need ? needLabel(need) : '—'}
                  </span>
                  <span className="qrow__id">{incident.id}</span>
                  {overdue ? (
                    <span className="tag tag--danger">No team</span>
                  ) : (
                    <span className={`pill pill--${incident.status}`}>{words(incident.status)}</span>
                  )}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
