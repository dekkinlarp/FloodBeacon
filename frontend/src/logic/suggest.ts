import type { Incident, Need, Skill, Team, TravelTime } from '../types';
import { vehicleCanServe } from './dispatch';
import { hoursSince } from './contactBadge';
import { BLOCK_ASSIGNMENT_HOURS } from './safety';

// Ranks teams for an incident. The system suggests; the dispatcher decides.
// Nothing here assigns a team.

/** Skills that earn the skill bonus for each need. */
export const NEED_SKILLS: Partial<Record<Need, Skill>> = {
  medical: 'first_aid',
  medication: 'first_aid',
  rescue: 'swimmer',
};
export const SKILL_MATCH_BONUS = 40; // per matched need skill
export const LANGUAGE_BONUS = 15;
/** Travel points fall linearly from TRAVEL_MAX_POINTS at 0 min to 0 at TRAVEL_ZERO_AT_MINUTES. */
export const TRAVEL_MAX_POINTS = 100;
export const TRAVEL_ZERO_AT_MINUTES = 240;
/** No fatigue penalty up to this many hours on duty. */
export const FATIGUE_FREE_HOURS = 8;
export const FATIGUE_PENALTY_PER_HOUR = 4;
/** Teams on duty longer than this are excluded (same limit that blocks assignment). */
export const MAX_HOURS_ON_DUTY = BLOCK_ASSIGNMENT_HOURS;
export const MAX_SUGGESTIONS = 3;

export type TeamEvaluation =
  | { team: Team; eligible: true; score: number; reasons: string[]; travelMinutes: number | null }
  | { team: Team; eligible: false; reasons: string[] };

export type TeamSuggestion = Extract<TeamEvaluation, { eligible: true }>;

const words = (s: string) => s.replace(/_/g, ' ');
const round1 = (n: number) => Math.round(n * 10) / 10;

export function travelMinutes(travelTimes: readonly TravelTime[], teamId: string, incidentId: string): number | null {
  return travelTimes.find((t) => t.team_id === teamId && t.incident_id === incidentId)?.minutes ?? null;
}

/** Scores one team, or says why it is excluded. */
export function evaluateTeam(
  incident: Incident,
  team: Team,
  travelTimes: readonly TravelTime[],
  now: Date,
): TeamEvaluation {
  const excluded: string[] = [];
  if (team.status !== 'available') excluded.push(`${words(team.status)}, not available`);
  if (!vehicleCanServe(team.vehicle, incident.access_type)) {
    excluded.push(`${words(team.vehicle)} cannot reach ${words(incident.access_type)}`);
  }
  if (incident.needs.includes('evacuation') && team.carry_capacity < incident.people_count) {
    excluded.push(`carries ${team.carry_capacity}, needs ${incident.people_count} evacuated`);
  }
  const hoursOnDuty = team.on_duty_since ? hoursSince(team.on_duty_since, now) : 0;
  if (hoursOnDuty > MAX_HOURS_ON_DUTY) {
    excluded.push(`on duty ${Math.floor(hoursOnDuty)} h (max ${MAX_HOURS_ON_DUTY} h)`);
  }
  if (excluded.length > 0) return { team, eligible: false, reasons: excluded };

  let score = 0;
  const reasons: string[] = [];

  const minutes = travelMinutes(travelTimes, team.id, incident.id);
  if (minutes === null) {
    reasons.push('Travel time unknown');
  } else {
    score += Math.max(0, TRAVEL_MAX_POINTS * (1 - minutes / TRAVEL_ZERO_AT_MINUTES));
    reasons.push(`About ${Math.round(minutes)} min away`);
  }

  const neededSkills = new Set(incident.needs.map((n) => NEED_SKILLS[n]).filter((s): s is Skill => !!s));
  for (const skill of neededSkills) {
    if (team.skills.includes(skill)) {
      score += SKILL_MATCH_BONUS;
      reasons.push(`Has ${words(skill)}`);
    } else {
      reasons.push(`No ${words(skill)}`);
    }
  }

  if (team.languages.includes(incident.reporter_language)) {
    score += LANGUAGE_BONUS;
    reasons.push(`Speaks ${incident.reporter_language}`);
  }

  if (hoursOnDuty > FATIGUE_FREE_HOURS) {
    score -= (hoursOnDuty - FATIGUE_FREE_HOURS) * FATIGUE_PENALTY_PER_HOUR;
    reasons.push(`On duty ${Math.floor(hoursOnDuty)} h`);
  }

  return { team, eligible: true, score: round1(score), reasons, travelMinutes: minutes };
}

/** Evaluations for every team: eligible ones best first, then excluded ones. */
export function evaluateTeams(
  incident: Incident,
  teams: readonly Team[],
  travelTimes: readonly TravelTime[],
  now: Date,
): TeamEvaluation[] {
  const all = teams.map((t) => evaluateTeam(incident, t, travelTimes, now));
  const eligible = all.filter((e): e is TeamSuggestion => e.eligible).sort(compareSuggestions);
  return [...eligible, ...all.filter((e) => !e.eligible)];
}

/** Top 3 eligible teams, best first. Empty when no team fits. */
export function suggestTeams(
  incident: Incident,
  teams: readonly Team[],
  travelTimes: readonly TravelTime[],
  now: Date,
): TeamSuggestion[] {
  return evaluateTeams(incident, teams, travelTimes, now)
    .filter((e): e is TeamSuggestion => e.eligible)
    .slice(0, MAX_SUGGESTIONS);
}

/** Higher score first; then shorter travel (unknown last); then team id. */
function compareSuggestions(a: TeamSuggestion, b: TeamSuggestion): number {
  return (
    b.score - a.score ||
    (a.travelMinutes ?? Infinity) - (b.travelMinutes ?? Infinity) ||
    a.team.id.localeCompare(b.team.id)
  );
}
