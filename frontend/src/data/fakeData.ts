import derna from '../../data/scenarios/derna-2023.json';
import nepal from '../../data/scenarios/nepal-2026.json';
import type { SiteId } from './sites';
import incidentsJson from '../../data/fake/incidents.json';
import healthJson from '../../data/fake/health.json';
import teamsJson from '../../data/fake/teams.json';
import travelTimesJson from '../../data/fake/travel-times.json';
import type { Health, Incident, Team, TravelTime } from '../types';
import { validateDataset, validateTravelTimes } from '../logic/validateData';
import { latestTimestamp, offsetToNow, shiftRecords } from '../logic/shiftTimes';

export interface DispatchData {
  incidents: Incident[];
  teams: Team[];
  health: Health[];
  travelTimes: TravelTime[];
}

const INCIDENT_TIMES = ['created_at', 'updated_at', 'last_contact_at'] as const;
const HEALTH_TIMES = ['updated_at'] as const;
const TEAM_TIMES = ['on_duty_since', 'last_check_in_at'] as const;

/** When shifting, the newest fake timestamp lands this long before "now". */
const SHIFT_LEAD_MS = 5 * 60 * 1000;

/**
 * Loads the fake data and checks it against src/types/ before anything uses it.
 * Selects one of the three fictional exercises; no database is involved.
 *
 * With `shiftTo`, every timestamp moves forward by the same amount so the
 * newest one is 5 minutes before that time (gaps unchanged). The app passes the
 * real clock so the 2 Oct fake data reads as recent; tests pass nothing.
 */
export function loadFakeData(options: { shiftTo?: Date; siteId?: SiteId } = {}): DispatchData {
  const dataset = options.siteId === 'derna-2023' ? derna : options.siteId === 'nepal-2026' ? nepal : {
    incidents: incidentsJson, health: healthJson, teams: teamsJson, travelTimes: travelTimesJson,
  };
  const { incidents: incidentsData, health: healthData, teams: teamsData, travelTimes: travelTimesData } = dataset;
  const errors = validateDataset({ incidents: incidentsData, health: healthData, teams: teamsData });
  errors.push(
    ...validateTravelTimes(
      travelTimesData,
      new Set(teamsData.map((t) => t.id)),
      new Set(incidentsData.map((i) => i.id)),
    ),
  );
  if (errors.length > 0) {
    // Messages name ids and fields only, never health values (see validateData).
    throw new Error(`Fake data is invalid:\n${errors.join('\n')}`);
  }
  // Safe after validation: JSON imports are typed with plain strings, not the enum unions.
  let incidents = incidentsData as Incident[];
  let health = healthData as Health[];
  let teams = teamsData as Team[];
  const travelTimes = travelTimesData as TravelTime[];

  if (options.shiftTo) {
    const latest = latestTimestamp([
      { records: incidents, fields: INCIDENT_TIMES },
      { records: health, fields: HEALTH_TIMES },
      { records: teams, fields: TEAM_TIMES },
    ]);
    if (latest !== null) {
      const offset = offsetToNow(latest, options.shiftTo, SHIFT_LEAD_MS);
      incidents = shiftRecords(incidents, INCIDENT_TIMES, offset);
      health = shiftRecords(health, HEALTH_TIMES, offset);
      teams = shiftRecords(teams, TEAM_TIMES, offset);
    }
  }
  return { incidents, teams, health, travelTimes };
}
