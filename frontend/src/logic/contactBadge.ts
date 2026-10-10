/** Badge turns red when the last contact is more than this many hours ago. */
export const CONTACT_OVERDUE_HOURS = 6;

const MS_PER_HOUR = 60 * 60 * 1000;

/** Whole and fractional hours from `iso` to `now`. Never negative. */
export function hoursSince(iso: string, now: Date): number {
  return Math.max(0, (now.getTime() - Date.parse(iso)) / MS_PER_HOUR);
}

export function formatHours(hours: number): string {
  return hours < 1 ? '<1h' : `${Math.floor(hours)}h`;
}

export interface ContactBadge {
  hours: number;
  label: string;
  overdue: boolean;
}

/**
 * Hours since we last heard from the people at an incident. When
 * `last_contact_at` is missing, the report itself (`created_at`) counts as
 * the last contact.
 */
export function contactBadge(
  incident: { last_contact_at: string | null; created_at: string },
  now: Date,
): ContactBadge {
  const hours = hoursSince(incident.last_contact_at ?? incident.created_at, now);
  return { hours, label: formatHours(hours), overdue: hours > CONTACT_OVERDUE_HOURS };
}
