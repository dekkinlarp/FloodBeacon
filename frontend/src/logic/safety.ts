import type { AccessType, Incident, Need, Team, TeamStatus } from '../types';
import { hoursSince } from './contactBadge';

// Responder safety: fatigue limits, check-in timer, required equipment.

/** From this many hours on duty, the team card and assign dialog suggest rest. */
export const SUGGEST_REST_HOURS = 12;
/** Above this many hours on duty, new assignments are blocked. */
export const BLOCK_ASSIGNMENT_HOURS = 16;

export type FatigueLevel = 'ok' | 'rest' | 'block';

export interface Fatigue {
  hours: number;
  level: FatigueLevel;
  /** 0–1 share of BLOCK_ASSIGNMENT_HOURS, for the fatigue bar. */
  fraction: number;
}

export function fatigue(team: Pick<Team, 'on_duty_since'>, now: Date): Fatigue {
  const hours = team.on_duty_since ? hoursSince(team.on_duty_since, now) : 0;
  const level: FatigueLevel = hours > BLOCK_ASSIGNMENT_HOURS ? 'block' : hours >= SUGGEST_REST_HOURS ? 'rest' : 'ok';
  return { hours, level, fraction: Math.min(1, hours / BLOCK_ASSIGNMENT_HOURS) };
}

/** Teams in the field must check in at least this often. */
export const CHECK_IN_INTERVAL_MINUTES = 60;
/** Statuses that count as "in the field". Teams at base do not need to check in. */
export const FIELD_STATUSES: readonly TeamStatus[] = ['en_route', 'on_scene', 'returning'];

export interface CheckInState {
  /** Whether this team must check in (it is in the field). */
  required: boolean;
  /** Minutes since the last check-in; null if never. */
  minutesSince: number | null;
  missed: boolean;
}

export function checkInState(team: Pick<Team, 'status' | 'last_check_in_at'>, now: Date): CheckInState {
  const minutesSince = team.last_check_in_at ? hoursSince(team.last_check_in_at, now) * 60 : null;
  const required = FIELD_STATUSES.includes(team.status);
  const missed = required && (minutesSince === null || minutesSince > CHECK_IN_INTERVAL_MINUTES);
  return { required, minutesSince, missed };
}

/** "never", "<1 min ago", "45 min ago", "2 h 05 min ago". */
export function formatCheckInAge(minutesSince: number | null): string {
  if (minutesSince === null) return 'never';
  const m = Math.floor(minutesSince);
  if (m < 1) return '<1 min ago';
  if (m < 60) return `${m} min ago`;
  return `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')} min ago`;
}

/** Field teams that have missed their check-in, longest overdue first. */
export function missedCheckIns<T extends Pick<Team, 'id' | 'status' | 'last_check_in_at'>>(
  teams: readonly T[],
  now: Date,
): { team: T; minutesSince: number | null }[] {
  return teams
    .map((team) => ({ team, ...checkInState(team, now) }))
    .filter((t) => t.missed)
    .sort((a, b) => (b.minutesSince ?? Infinity) - (a.minutesSince ?? Infinity) || a.team.id.localeCompare(b.team.id))
    .map(({ team, minutesSince }) => ({ team, minutesSince }));
}

/** Equipment a team should carry, by access type and need. Names match `Team.equipment`. */
export const ACCESS_EQUIPMENT: Record<AccessType, readonly string[]> = {
  truck: [],
  boat_only: ['life jackets'],
  walk_only: ['wading poles', 'life jackets'],
};
export const NEED_EQUIPMENT: Partial<Record<Need, readonly string[]>> = {
  rescue: ['throw bag', 'life jackets'],
  medical: ['first aid kit'],
  evacuation: ['life jackets'],
  food_water: ['drinking water'],
};

export function requiredEquipment(incident: Pick<Incident, 'access_type' | 'needs'>): string[] {
  const items = [...ACCESS_EQUIPMENT[incident.access_type], ...incident.needs.flatMap((n) => NEED_EQUIPMENT[n] ?? [])];
  return [...new Set(items)];
}

export function equipmentCheck(
  incident: Pick<Incident, 'access_type' | 'needs'>,
  team: Pick<Team, 'equipment'>,
): { item: string; carried: boolean }[] {
  const carried = new Set(team.equipment.map((e) => e.toLowerCase()));
  return requiredEquipment(incident).map((item) => ({ item, carried: carried.has(item) }));
}
