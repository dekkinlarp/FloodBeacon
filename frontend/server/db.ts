import pg from 'pg';
import type { DispatchState } from '../src/logic/dispatch';

// Reads and writes the whole dispatch state. The dataset is small (one city's
// active incidents), so the server loads it all, runs the same pure rules as
// the browser, and writes back only the rows that changed.

// Timestamps come back as ISO 8601 strings, the format src/types/ uses.
const parseTimestamptz = pg.types.getTypeParser(pg.types.builtins.TIMESTAMPTZ);
pg.types.setTypeParser(pg.types.builtins.TIMESTAMPTZ, (v: string) => (parseTimestamptz(v) as Date).toISOString());
// numeric (water depth, travel minutes) as JS numbers.
pg.types.setTypeParser(pg.types.builtins.NUMERIC, (v: string) => Number(v));

export type Db = pg.Pool | pg.PoolClient | pg.Client;

export const DEFAULT_DATABASE_URL = 'postgresql://localhost:5432/floodbeacon';

export function createPool(): pg.Pool {
  return new pg.Pool({ connectionString: process.env.DATABASE_URL ?? DEFAULT_DATABASE_URL, max: 5 });
}

const point = (prefix: string, col: string) =>
  `ST_Y(${col}::geometry) AS ${prefix}lat, ST_X(${col}::geometry) AS ${prefix}lon`;

type Row = Record<string, unknown>;

export async function loadState(db: Db): Promise<DispatchState> {
  const q = async (sql: string) => (await db.query(sql)).rows as Row[];
  const [incidents, health, teams, assignments, feedback, travelTimes, routePlans, alerts, events] = await Promise.all([
    q(`SELECT id, created_at, updated_at, status, severity, access_type, district, ${point('', 'location')},
              address_note, needs::text[] AS needs, people_count, reporter_language, contact_phone, last_contact_at,
              source, original_message, ai_extracted, verified_by_human
       FROM incidents ORDER BY id`),
    q(`SELECT incident_id, priority, medical_needs::text[] AS medical_needs, mobility, vulnerable, injuries,
              supplies_left, notes, ai_extracted, verified_by_human, updated_at
       FROM health ORDER BY incident_id`),
    q(`SELECT id, name, status, vehicle, skills::text[] AS skills, languages::text[] AS languages, members_count,
              carry_capacity, equipment, ${point('base_', 'base_location')}, ${point('cur_', 'current_location')},
              on_duty_since, last_check_in_at
       FROM teams ORDER BY id`),
    q(`SELECT id, incident_id, team_id, role, assigned_at, assigned_by, ended_at, end_reason FROM assignments ORDER BY id`),
    q(`SELECT id, incident_id, team_id, submitted_at, submitted_by, water_depth_cm, route_worked, blocked_routes,
              people_helped, outcome, photo_ref
       FROM field_feedback ORDER BY id`),
    q(`SELECT team_id, incident_id, minutes FROM travel_times ORDER BY team_id, incident_id`),
    q(`SELECT incident_id, team_id, legs, reason, updated_at FROM route_plans ORDER BY incident_id, team_id`),
    q(`SELECT id, created_at, message, incident_id, team_id, acknowledged_at FROM alerts ORDER BY id`),
    q(`SELECT id, occurred_at, actor, entity_type, entity_id, event_type, from_value, to_value, note
       FROM events ORDER BY occurred_at, length(id), id`),
  ]);

  return {
    incidents: incidents.map(({ lat, lon, ...r }) => ({ ...r, location: { lat, lon } })) as unknown as DispatchState['incidents'],
    health: health as unknown as DispatchState['health'],
    teams: teams.map(({ base_lat, base_lon, cur_lat, cur_lon, ...r }) => ({
      ...r,
      base_location: { lat: base_lat, lon: base_lon },
      current_location: { lat: cur_lat, lon: cur_lon },
    })) as unknown as DispatchState['teams'],
    assignments: assignments as unknown as DispatchState['assignments'],
    feedback: feedback as unknown as DispatchState['feedback'],
    travelTimes: travelTimes as unknown as DispatchState['travelTimes'],
    routePlans: routePlans as unknown as DispatchState['routePlans'],
    alerts: alerts as unknown as DispatchState['alerts'],
    events: events as unknown as DispatchState['events'],
  };
}

/** Records in `after` that are new or different from `before`, matched by `key`. */
export function changed<T>(before: readonly T[], after: readonly T[], key: (x: T) => string): T[] {
  const old = new Map(before.map((x) => [key(x), JSON.stringify(x)]));
  return after.filter((x) => old.get(key(x)) !== JSON.stringify(x));
}

const geo = (n: number) => `ST_SetSRID(ST_MakePoint($${n + 1}, $${n}), 4326)::geography`;

/** Writes every row that differs between `before` and `after`. Call inside a transaction. */
export async function saveChanges(db: Db, before: DispatchState, after: DispatchState): Promise<void> {
  for (const i of changed(before.incidents, after.incidents, (x) => x.id)) {
    await db.query(
      `INSERT INTO incidents (id, created_at, updated_at, status, severity, access_type, district, location, address_note,
         needs, people_count, reporter_language, contact_phone, last_contact_at, source, original_message, ai_extracted,
         verified_by_human)
       VALUES ($1, $2, $3, $4, $5, $6, $7, ${geo(8)}, $10, $11::need[], $12, $13, $14, $15, $16, $17, $18, $19)
       ON CONFLICT (id) DO UPDATE SET created_at = EXCLUDED.created_at, updated_at = EXCLUDED.updated_at,
         status = EXCLUDED.status, severity = EXCLUDED.severity, access_type = EXCLUDED.access_type,
         district = EXCLUDED.district, location = EXCLUDED.location, address_note = EXCLUDED.address_note,
         needs = EXCLUDED.needs, people_count = EXCLUDED.people_count, reporter_language = EXCLUDED.reporter_language,
         contact_phone = EXCLUDED.contact_phone, last_contact_at = EXCLUDED.last_contact_at, source = EXCLUDED.source,
         original_message = EXCLUDED.original_message, ai_extracted = EXCLUDED.ai_extracted,
         verified_by_human = EXCLUDED.verified_by_human`,
      [i.id, i.created_at, i.updated_at, i.status, i.severity, i.access_type, i.district, i.location.lat, i.location.lon,
        i.address_note, i.needs, i.people_count, i.reporter_language, i.contact_phone, i.last_contact_at, i.source,
        i.original_message, i.ai_extracted, i.verified_by_human],
    );
  }
  for (const h of changed(before.health, after.health, (x) => x.incident_id)) {
    await db.query(
      `INSERT INTO health (incident_id, priority, medical_needs, mobility, vulnerable, injuries, supplies_left, notes,
         ai_extracted, verified_by_human, updated_at)
       VALUES ($1, $2, $3::medical_need[], $4, $5::jsonb, $6, $7, $8, $9, $10, $11)
       ON CONFLICT (incident_id) DO UPDATE SET priority = EXCLUDED.priority, medical_needs = EXCLUDED.medical_needs,
         mobility = EXCLUDED.mobility, vulnerable = EXCLUDED.vulnerable, injuries = EXCLUDED.injuries,
         supplies_left = EXCLUDED.supplies_left, notes = EXCLUDED.notes, ai_extracted = EXCLUDED.ai_extracted,
         verified_by_human = EXCLUDED.verified_by_human, updated_at = EXCLUDED.updated_at`,
      [h.incident_id, h.priority, h.medical_needs, h.mobility, JSON.stringify(h.vulnerable), h.injuries, h.supplies_left,
        h.notes, h.ai_extracted, h.verified_by_human, h.updated_at],
    );
  }
  for (const t of changed(before.teams, after.teams, (x) => x.id)) {
    await db.query(
      `INSERT INTO teams (id, name, status, vehicle, skills, languages, members_count, carry_capacity, equipment,
         base_location, current_location, on_duty_since, last_check_in_at)
       VALUES ($1, $2, $3, $4, $5::skill[], $6::language[], $7, $8, $9, ${geo(10)}, ${geo(12)}, $14, $15)
       ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, status = EXCLUDED.status, vehicle = EXCLUDED.vehicle,
         skills = EXCLUDED.skills, languages = EXCLUDED.languages, members_count = EXCLUDED.members_count,
         carry_capacity = EXCLUDED.carry_capacity, equipment = EXCLUDED.equipment, base_location = EXCLUDED.base_location,
         current_location = EXCLUDED.current_location, on_duty_since = EXCLUDED.on_duty_since,
         last_check_in_at = EXCLUDED.last_check_in_at`,
      [t.id, t.name, t.status, t.vehicle, t.skills, t.languages, t.members_count, t.carry_capacity, t.equipment,
        t.base_location.lat, t.base_location.lon, t.current_location.lat, t.current_location.lon, t.on_duty_since,
        t.last_check_in_at],
    );
  }
  for (const a of changed(before.assignments, after.assignments, (x) => x.id)) {
    await db.query(
      `INSERT INTO assignments (id, incident_id, team_id, role, assigned_at, assigned_by, ended_at, end_reason)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
       ON CONFLICT (id) DO UPDATE SET ended_at = EXCLUDED.ended_at, end_reason = EXCLUDED.end_reason`,
      [a.id, a.incident_id, a.team_id, a.role, a.assigned_at, a.assigned_by, a.ended_at, a.end_reason],
    );
  }
  for (const f of changed(before.feedback, after.feedback, (x) => x.id)) {
    await db.query(
      `INSERT INTO field_feedback (id, incident_id, team_id, submitted_at, submitted_by, water_depth_cm, route_worked,
         blocked_routes, people_helped, outcome, photo_ref)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) ON CONFLICT (id) DO NOTHING`,
      [f.id, f.incident_id, f.team_id, f.submitted_at, f.submitted_by, f.water_depth_cm, f.route_worked,
        f.blocked_routes, f.people_helped, f.outcome, f.photo_ref],
    );
  }
  for (const t of changed(before.travelTimes, after.travelTimes, (x) => `${x.team_id}|${x.incident_id}`)) {
    await db.query(
      `INSERT INTO travel_times (team_id, incident_id, minutes) VALUES ($1, $2, $3)
       ON CONFLICT (team_id, incident_id) DO UPDATE SET minutes = EXCLUDED.minutes`,
      [t.team_id, t.incident_id, t.minutes],
    );
  }
  for (const r of changed(before.routePlans, after.routePlans, (x) => `${x.incident_id}|${x.team_id}`)) {
    await db.query(
      `INSERT INTO route_plans (incident_id, team_id, legs, reason, updated_at) VALUES ($1, $2, $3::jsonb, $4, $5)
       ON CONFLICT (incident_id, team_id) DO UPDATE SET legs = EXCLUDED.legs, reason = EXCLUDED.reason,
         updated_at = EXCLUDED.updated_at`,
      [r.incident_id, r.team_id, JSON.stringify(r.legs), r.reason, r.updated_at],
    );
  }
  for (const a of changed(before.alerts, after.alerts, (x) => x.id)) {
    await db.query(
      `INSERT INTO alerts (id, created_at, message, incident_id, team_id, acknowledged_at) VALUES ($1, $2, $3, $4, $5, $6)
       ON CONFLICT (id) DO UPDATE SET acknowledged_at = EXCLUDED.acknowledged_at`,
      [a.id, a.created_at, a.message, a.incident_id, a.team_id, a.acknowledged_at],
    );
  }
  // Events are append-only: insert the new ones, never update.
  const known = new Set(before.events.map((e) => e.id));
  for (const e of after.events.filter((x) => !known.has(x.id))) {
    await db.query(
      `INSERT INTO events (id, occurred_at, actor, entity_type, entity_id, event_type, from_value, to_value, note)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
      [e.id, e.occurred_at, e.actor, e.entity_type, e.entity_id, e.event_type, e.from_value, e.to_value, e.note],
    );
  }
}
