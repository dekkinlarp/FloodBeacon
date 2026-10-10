import type { AssignmentEndReason, AssignmentRole } from './enums';

export interface Assignment {
  id: string;
  incident_id: string;
  team_id: string;
  role: AssignmentRole;
  assigned_at: string;
  assigned_by: string;
  ended_at: string | null;
  end_reason: AssignmentEndReason | null;
}
