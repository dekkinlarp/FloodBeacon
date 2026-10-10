import type { Incident, IncidentStatus, Team } from '../types';
import { isOverdueCritical } from './warnings';

const CLOSED: readonly IncidentStatus[] = ['resolved', 'cancelled'];
const WAITING: readonly IncidentStatus[] = ['new', 'verified', 'could_not_reach'];

export interface BoardSummary {
  /** Not resolved or cancelled. */
  open: number;
  /** Open and critical. */
  critical: number;
  /** Open with no team working it (new, verified, could_not_reach). */
  waiting: number;
  /** Critical, no team, reported more than 30 min ago. */
  overdueCritical: number;
  teamsAvailable: number;
  teamsOnDuty: number;
}

/** Counts for the dispatch header. */
export function boardSummary(incidents: readonly Incident[], teams: readonly Team[], now: Date): BoardSummary {
  const open = incidents.filter((i) => !CLOSED.includes(i.status));
  return {
    open: open.length,
    critical: open.filter((i) => i.severity === 'critical').length,
    waiting: open.filter((i) => WAITING.includes(i.status)).length,
    overdueCritical: incidents.filter((i) => isOverdueCritical(i, now)).length,
    teamsAvailable: teams.filter((t) => t.status === 'available').length,
    teamsOnDuty: teams.filter((t) => t.status !== 'off_duty').length,
  };
}
