import type { Language, Skill, TeamStatus, Vehicle } from './enums';
import type { LatLon } from './location';

export interface Team {
  id: string;
  name: string;
  status: TeamStatus;
  vehicle: Vehicle;
  skills: Skill[];
  languages: Language[];
  members_count: number;
  /** How many people the team can evacuate in one trip. */
  carry_capacity: number;
  /** Free text, e.g. "life jackets", "stretcher". */
  equipment: string[];
  base_location: LatLon;
  current_location: LatLon;
  /** Start of the current shift; null while off duty. */
  on_duty_since: string | null;
  /** Last time the team reported in (radio/app); null if never. */
  last_check_in_at: string | null;
}
