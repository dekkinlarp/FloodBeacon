import type { DispatchState } from './dispatch';

export interface DemoScore {
  resolved: number;
  /** Mean minutes from report (created_at) to the team first being on scene. Null if none yet. */
  avgResponseMinutes: number | null;
  /** Sum of people helped in field feedback. */
  peopleReached: number;
  teamsResting: number;
}

export function demoScore(state: DispatchState): DemoScore {
  const firstOnScene = new Map<string, number>();
  for (const e of state.events) {
    if (e.entity_type === 'incident' && e.event_type === 'status_changed' && e.to_value === 'on_scene' && !firstOnScene.has(e.entity_id)) {
      firstOnScene.set(e.entity_id, Date.parse(e.occurred_at));
    }
  }
  const responses = state.incidents
    .filter((i) => firstOnScene.has(i.id))
    .map((i) => (firstOnScene.get(i.id)! - Date.parse(i.created_at)) / 60_000);
  return {
    resolved: state.incidents.filter((i) => i.status === 'resolved').length,
    avgResponseMinutes: responses.length ? responses.reduce((a, b) => a + b, 0) / responses.length : null,
    peopleReached: state.feedback.reduce((sum, f) => sum + f.people_helped, 0),
    teamsResting: state.teams.filter((t) => t.status === 'resting').length,
  };
}
