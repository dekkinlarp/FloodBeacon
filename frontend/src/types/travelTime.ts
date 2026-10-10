/**
 * Estimated travel time for a team to reach an incident.
 * Stand-in for Person 2's routes; shape will change to match theirs.
 */
export interface TravelTime {
  team_id: string;
  incident_id: string;
  minutes: number;
}
