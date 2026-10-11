import type { Health, Need } from '../types';

export interface EmergencyReminder {
  kind: 'medical' | 'rescue';
  label: string;
}

/** Demo escalation labels; these are not local emergency contact numbers. */
export function emergencyReminders(
  incident: { needs: readonly Need[] },
  health: Pick<Health, 'priority'> | undefined,
): EmergencyReminder[] {
  const out: EmergencyReminder[] = [];
  if (health?.priority === 'critical') out.push({ kind: 'medical', label: 'Medical escalation — critical exercise case' });
  if (incident.needs.includes('rescue')) out.push({ kind: 'rescue', label: 'Rescue escalation — exercise case' });
  return out;
}
