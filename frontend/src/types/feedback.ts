import type { FeedbackOutcome } from './enums';

/** Report from a field team after (trying to) reach an incident. */
export interface FieldFeedback {
  id: string;
  incident_id: string;
  team_id: string;
  submitted_at: string;
  submitted_by: string;
  /** Measured water depth at the incident, in centimetres. Null if not measured. */
  water_depth_cm: number | null;
  route_worked: boolean;
  /** Free text: blocked roads, bridges, canals. Empty if none. */
  blocked_routes: string;
  people_helped: number;
  outcome: FeedbackOutcome;
  /** Reference to a photo (file name for now; file storage still to be decided). */
  photo_ref: string | null;
}
