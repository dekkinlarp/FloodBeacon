/**
 * How a team gets to an incident, leg by leg. Stand-in until Person 2's
 * routes exist; keep the shape small so it is easy to replace.
 */
export const ROUTE_MODES = ['truck', 'boat', 'walk'] as const;
export type RouteMode = (typeof ROUTE_MODES)[number];

export interface RouteLeg {
  mode: RouteMode;
  minutes: number;
}

export interface RoutePlan {
  incident_id: string;
  team_id: string;
  legs: RouteLeg[];
  /** Why the route is what it is, e.g. "bridge closed". */
  reason: string | null;
  updated_at: string;
}
