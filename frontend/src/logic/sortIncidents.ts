import type { Incident } from '../types';
import { severityRank } from './severity';
import { isOverdueCritical } from './warnings';

/**
 * Overdue critical incidents (no team after 30 min) first; then most severe;
 * within a severity, longest waiting first (earliest `created_at`). Ties fall
 * back to id so the order is stable. Returns a new array.
 */
export function sortIncidents(incidents: readonly Incident[], now: Date): Incident[] {
  const overdue = (i: Incident) => (isOverdueCritical(i, now) ? 0 : 1);
  return [...incidents].sort(
    (a, b) =>
      overdue(a) - overdue(b) ||
      severityRank(a.severity) - severityRank(b.severity) ||
      Date.parse(a.created_at) - Date.parse(b.created_at) ||
      a.id.localeCompare(b.id),
  );
}
