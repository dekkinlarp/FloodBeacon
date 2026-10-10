/** Something the dispatcher must notice (route change, hazard). Never holds health details. */
export interface DispatchAlert {
  id: string;
  created_at: string;
  message: string;
  incident_id: string | null;
  team_id: string | null;
  acknowledged_at: string | null;
}
