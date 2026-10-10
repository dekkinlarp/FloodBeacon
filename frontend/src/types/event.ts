import type { EventEntityType, EventType } from './enums';

/**
 * Append-only log entry, one per state change. `from_value` / `to_value` hold
 * statuses or ids only — never health details.
 */
export interface Event {
  id: string;
  occurred_at: string;
  actor: string; // user id, or 'system'
  entity_type: EventEntityType;
  entity_id: string;
  event_type: EventType;
  from_value: string | null;
  to_value: string | null;
  note: string | null;
}
