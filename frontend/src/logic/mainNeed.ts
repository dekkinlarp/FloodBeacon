import type { Need } from '../types';

/** The need shown as the marker icon: the first one listed on the incident. */
export function mainNeed(incident: { needs: readonly Need[] }): Need | null {
  return incident.needs[0] ?? null;
}
