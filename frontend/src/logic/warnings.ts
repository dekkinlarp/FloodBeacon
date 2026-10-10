import type { Incident, IncidentStatus } from '../types';
import { hoursSince } from './contactBadge';

/** Critical incidents waiting longer than this without a team are flagged. */
export const CRITICAL_UNASSIGNED_MINUTES = 30;

/** Statuses in which no team is working the incident. */
const UNASSIGNED_STATUSES: readonly IncidentStatus[] = ['new', 'verified', 'could_not_reach'];

/** Critical, still without a team, and reported more than 30 minutes ago. */
export function isOverdueCritical(incident: Incident, now: Date): boolean {
  return (
    incident.severity === 'critical' &&
    UNASSIGNED_STATUSES.includes(incident.status) &&
    hoursSince(incident.created_at, now) * 60 > CRITICAL_UNASSIGNED_MINUTES
  );
}
