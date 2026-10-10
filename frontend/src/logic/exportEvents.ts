import type { Event } from '../types';

// Event log export for Person 4 (validation). Events hold ids and statuses
// only, never health details, so the export is safe to share within the team.

export const EVENT_COLUMNS = [
  'id',
  'occurred_at',
  'actor',
  'entity_type',
  'entity_id',
  'event_type',
  'from_value',
  'to_value',
  'note',
] as const satisfies readonly (keyof Event)[];

export function eventsToJson(events: readonly Event[]): string {
  return JSON.stringify(events, null, 2);
}

/**
 * RFC 4180 cell: quoted when it contains a comma, quote or line break.
 * Cells starting with = + - @ get a leading apostrophe so spreadsheet apps
 * don't run them as formulas.
 */
export function csvCell(value: string | null): string {
  if (value === null) return '';
  const safe = /^[=+\-@]/.test(value) ? `'${value}` : value;
  return /[",\r\n]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
}

export function eventsToCsv(events: readonly Event[]): string {
  const rows = [EVENT_COLUMNS.join(','), ...events.map((e) => EVENT_COLUMNS.map((c) => csvCell(e[c])).join(','))];
  return rows.join('\r\n') + '\r\n';
}

/** File name like `dispatch-events-2026-10-03T09-15-00Z.csv`. */
export function exportFileName(now: Date, ext: 'json' | 'csv'): string {
  const stamp = now.toISOString().replace(/\.\d{3}Z$/, 'Z').replace(/:/g, '-');
  return `dispatch-events-${stamp}.${ext}`;
}
