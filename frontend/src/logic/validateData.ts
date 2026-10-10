import {
  ACCESS_TYPES,
  INCIDENT_SOURCES,
  INCIDENT_STATUSES,
  LANGUAGES,
  MEDICAL_NEEDS,
  MOBILITY_LEVELS,
  NEEDS,
  SEVERITIES,
  SKILLS,
  TEAM_STATUSES,
  VEHICLES,
} from '../types';

// Runtime checks that unknown data (fake JSON now, PostgreSQL rows later) matches
// src/types/. Each validator returns a list of problems; empty means valid.
// Messages name fields and ids only — never field values from health records.

const VULNERABLE_GROUPS = ['elderly', 'children', 'pregnant', 'disabled'] as const;

/** Bounding box used for fake data. Covers all 50 Bangkok districts. */
export const BANGKOK_BOUNDS = { minLat: 13.6, maxLat: 13.95, minLon: 100.35, maxLon: 100.95 };

type Rec = Record<string, unknown>;

function isRecord(v: unknown): v is Rec {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function isIsoDateTime(v: unknown): boolean {
  return typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(v) && !Number.isNaN(Date.parse(v));
}

class Checker {
  readonly errors: string[] = [];
  constructor(
    private readonly obj: Rec,
    private readonly where: string,
  ) {}

  private fail(field: string, msg: string) {
    this.errors.push(`${this.where}.${field}: ${msg}`);
  }

  string(field: string, opts: { nullable?: boolean; nonEmpty?: boolean } = {}) {
    const v = this.obj[field];
    if (v === null && opts.nullable) return;
    if (typeof v !== 'string') return this.fail(field, 'expected string');
    if (opts.nonEmpty && v.trim() === '') this.fail(field, 'must not be empty');
  }

  boolean(field: string) {
    if (typeof this.obj[field] !== 'boolean') this.fail(field, 'expected boolean');
  }

  integer(field: string, min: number) {
    const v = this.obj[field];
    if (typeof v !== 'number' || !Number.isInteger(v) || v < min) {
      this.fail(field, `expected integer >= ${min}`);
    }
  }

  dateTime(field: string, opts: { nullable?: boolean } = {}) {
    const v = this.obj[field];
    if (v === null && opts.nullable) return;
    if (!isIsoDateTime(v)) this.fail(field, 'expected ISO 8601 date-time');
  }

  oneOf(field: string, allowed: readonly string[]) {
    const v = this.obj[field];
    if (typeof v !== 'string' || !allowed.includes(v)) {
      this.fail(field, `expected one of ${allowed.join(', ')}`);
    }
  }

  listOf(field: string, allowed: readonly string[], opts: { nonEmpty?: boolean } = {}) {
    const v = this.obj[field];
    if (!Array.isArray(v)) return this.fail(field, 'expected array');
    if (opts.nonEmpty && v.length === 0) this.fail(field, 'must not be empty');
    if (v.some((x) => typeof x !== 'string' || !allowed.includes(x))) {
      this.fail(field, `items must be one of ${allowed.join(', ')}`);
    }
    if (new Set(v).size !== v.length) this.fail(field, 'duplicate items');
  }

  stringList(field: string) {
    const v = this.obj[field];
    if (!Array.isArray(v) || v.some((x) => typeof x !== 'string' || x.trim() === '')) {
      this.fail(field, 'expected array of non-empty strings');
    }
  }

  location(field: string) {
    const v = this.obj[field];
    if (!isRecord(v) || typeof v.lat !== 'number' || typeof v.lon !== 'number') {
      return this.fail(field, 'expected { lat: number, lon: number }');
    }
    const b = BANGKOK_BOUNDS;
    if (v.lat < b.minLat || v.lat > b.maxLat || v.lon < b.minLon || v.lon > b.maxLon) {
      this.fail(field, 'outside Bangkok bounds');
    }
  }
}

function label(prefix: string, i: number, obj: unknown): string {
  const id = isRecord(obj) && typeof obj.id === 'string' ? obj.id : isRecord(obj) && typeof obj.incident_id === 'string' ? obj.incident_id : `#${i}`;
  return `${prefix}[${id}]`;
}

export function validateIncident(value: unknown, where = 'incident'): string[] {
  if (!isRecord(value)) return [`${where}: expected object`];
  const c = new Checker(value, where);
  c.string('id', { nonEmpty: true });
  c.dateTime('created_at');
  c.dateTime('updated_at');
  c.oneOf('status', INCIDENT_STATUSES);
  c.oneOf('severity', SEVERITIES);
  c.oneOf('access_type', ACCESS_TYPES);
  c.string('district', { nonEmpty: true });
  c.location('location');
  c.string('address_note');
  c.listOf('needs', NEEDS, { nonEmpty: true });
  c.integer('people_count', 1);
  c.oneOf('reporter_language', LANGUAGES);
  c.string('contact_phone', { nullable: true });
  c.dateTime('last_contact_at', { nullable: true });
  c.oneOf('source', INCIDENT_SOURCES);
  c.string('original_message', { nullable: true });
  c.boolean('ai_extracted');
  c.boolean('verified_by_human');

  // Rule 8: AI-extracted fields must be traceable to the original message.
  if (value.ai_extracted === true && typeof value.original_message !== 'string') {
    c.errors.push(`${where}.original_message: required when ai_extracted is true`);
  }
  if (value.source === 'sms' && typeof value.original_message !== 'string') {
    c.errors.push(`${where}.original_message: required when source is sms`);
  }
  if (isIsoDateTime(value.created_at) && isIsoDateTime(value.updated_at)) {
    if (Date.parse(value.updated_at as string) < Date.parse(value.created_at as string)) {
      c.errors.push(`${where}.updated_at: earlier than created_at`);
    }
  }
  return c.errors;
}

export function validateHealth(value: unknown, where = 'health'): string[] {
  if (!isRecord(value)) return [`${where}: expected object`];
  const c = new Checker(value, where);
  c.string('incident_id', { nonEmpty: true });
  c.oneOf('priority', SEVERITIES);
  c.listOf('medical_needs', MEDICAL_NEEDS);
  c.oneOf('mobility', MOBILITY_LEVELS);
  const v = value.vulnerable;
  if (!isRecord(v) || VULNERABLE_GROUPS.some((g) => typeof v[g] !== 'number' || !Number.isInteger(v[g]) || (v[g] as number) < 0)) {
    c.errors.push(`${where}.vulnerable: expected { ${VULNERABLE_GROUPS.join(', ')} } as integers >= 0`);
  }
  c.stringList('injuries');
  c.string('supplies_left', { nullable: true });
  c.string('notes');
  c.boolean('ai_extracted');
  c.boolean('verified_by_human');
  c.dateTime('updated_at');
  return c.errors;
}

export function validateTeam(value: unknown, where = 'team'): string[] {
  if (!isRecord(value)) return [`${where}: expected object`];
  const c = new Checker(value, where);
  c.string('id', { nonEmpty: true });
  c.string('name', { nonEmpty: true });
  c.oneOf('status', TEAM_STATUSES);
  c.oneOf('vehicle', VEHICLES);
  c.listOf('skills', SKILLS);
  c.listOf('languages', LANGUAGES, { nonEmpty: true });
  c.integer('members_count', 1);
  c.integer('carry_capacity', 0);
  c.stringList('equipment');
  c.location('base_location');
  c.location('current_location');
  c.dateTime('on_duty_since', { nullable: true });
  c.dateTime('last_check_in_at', { nullable: true });
  if (value.status === 'off_duty' && value.on_duty_since !== null) {
    c.errors.push(`${where}.on_duty_since: must be null when off_duty`);
  }
  if (value.status !== 'off_duty' && value.on_duty_since === null) {
    c.errors.push(`${where}.on_duty_since: required unless off_duty`);
  }
  return c.errors;
}

export function validateTravelTimes(value: unknown, teamIds: ReadonlySet<string>, incidentIds: ReadonlySet<string>): string[] {
  if (!Array.isArray(value)) return ['travelTimes: expected array'];
  const errors: string[] = [];
  const seen = new Set<string>();
  value.forEach((x, i) => {
    const where = `travelTimes[${i}]`;
    if (!isRecord(x)) return errors.push(`${where}: expected object`);
    const c = new Checker(x, where);
    c.string('team_id', { nonEmpty: true });
    c.string('incident_id', { nonEmpty: true });
    if (typeof x.minutes !== 'number' || !Number.isFinite(x.minutes) || x.minutes < 0) {
      c.errors.push(`${where}.minutes: expected number >= 0`);
    }
    if (!teamIds.has(x.team_id as string)) c.errors.push(`${where}.team_id: not found in teams`);
    if (!incidentIds.has(x.incident_id as string)) c.errors.push(`${where}.incident_id: not found in incidents`);
    const key = `${String(x.team_id)}|${String(x.incident_id)}`;
    if (seen.has(key)) c.errors.push(`${where}: duplicate team/incident pair`);
    seen.add(key);
    errors.push(...c.errors);
  });
  return errors;
}

function duplicateIds(items: unknown[], key: string, prefix: string): string[] {
  const seen = new Set<unknown>();
  const errors: string[] = [];
  for (const item of items) {
    if (!isRecord(item)) continue;
    const id = item[key];
    if (seen.has(id)) errors.push(`${prefix}: duplicate ${key} ${String(id)}`);
    seen.add(id);
  }
  return errors;
}

/** Validates each record plus cross-references between the collections. */
export function validateDataset(data: {
  incidents: unknown;
  health: unknown;
  teams: unknown;
}): string[] {
  const errors: string[] = [];
  const { incidents, health, teams } = data;
  if (!Array.isArray(incidents)) errors.push('incidents: expected array');
  if (!Array.isArray(health)) errors.push('health: expected array');
  if (!Array.isArray(teams)) errors.push('teams: expected array');
  if (!Array.isArray(incidents) || !Array.isArray(health) || !Array.isArray(teams)) return errors;

  incidents.forEach((x, i) => errors.push(...validateIncident(x, label('incidents', i, x))));
  health.forEach((x, i) => errors.push(...validateHealth(x, label('health', i, x))));
  teams.forEach((x, i) => errors.push(...validateTeam(x, label('teams', i, x))));

  errors.push(...duplicateIds(incidents, 'id', 'incidents'));
  errors.push(...duplicateIds(health, 'incident_id', 'health'));
  errors.push(...duplicateIds(teams, 'id', 'teams'));

  const incidentIds = new Set(incidents.filter(isRecord).map((x) => x.id));
  const healthIds = new Set(health.filter(isRecord).map((x) => x.incident_id));
  for (const h of health.filter(isRecord)) {
    if (!incidentIds.has(h.incident_id)) {
      errors.push(`health[${String(h.incident_id)}]: incident_id not found in incidents`);
    }
  }
  for (const inc of incidents.filter(isRecord)) {
    if (Array.isArray(inc.needs) && inc.needs.includes('medical') && !healthIds.has(inc.id)) {
      errors.push(`incidents[${String(inc.id)}]: has 'medical' need but no health record`);
    }
  }
  return errors;
}
