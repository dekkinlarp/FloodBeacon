import type { Health, Need } from '../types';

export interface EmergencyReminder {
  number: '1669' | '1784';
  label: string;
}

/**
 * Reminders shown on the incident card (CLAUDE.md rule 9).
 * 1669 when the health record is critical; 1784 when the incident needs rescue.
 * Exact definition of "critical medical" is still open (PLAN.md Q11).
 */
export function emergencyReminders(
  incident: { needs: readonly Need[] },
  health: Pick<Health, 'priority'> | undefined,
): EmergencyReminder[] {
  const out: EmergencyReminder[] = [];
  if (health?.priority === 'critical') {
    out.push({ number: '1669', label: 'Call 1669 — critical medical case (emergency medical service)' });
  }
  if (incident.needs.includes('rescue')) {
    out.push({ number: '1784', label: 'Call 1784 — rescue case (DDPM)' });
  }
  return out;
}
