import { useState } from 'react';
import type { Incident, IncidentStatus, Team } from '../types';
import type { DispatchState } from '../logic/dispatch';
import { activeAssignmentsForIncident, canAssign, nextIncidentStatuses } from '../logic/dispatch';
import type { TeamSuggestion } from '../logic/suggest';
import { AssignDialog } from './AssignDialog';
import { SuggestionList } from './SuggestionList';

interface Props {
  state: DispatchState;
  incident: Incident;
  now: Date;
  suggestions: readonly TeamSuggestion[];
  onAssign: (teamId: string, backup: boolean) => void;
  onStatus: (to: IncidentStatus) => void;
  onRecall: (teamId: string) => void;
}

const words = (s: string) => s.replace(/_/g, ' ');

/** Status actions, teams on the incident, suggestions and the full team list. */
export function IncidentDispatchPanel({ state, incident, now, suggestions, onAssign, onStatus, onRecall }: Props) {
  const [pending, setPending] = useState<{ team: Team; backup: boolean } | null>(null);
  const active = activeAssignmentsForIncident(state, incident.id);
  const nextStatuses = nextIncidentStatuses(incident.status);
  const teamName = (id: string) => state.teams.find((t) => t.id === id)?.name ?? id;

  return (
    <section className="section">
      <h3 className="section__title">Dispatch</h3>

      {nextStatuses.length > 0 && (
        <div className="actions">
          {nextStatuses.map((to) => (
            <button key={to} type="button" className="btn" onClick={() => onStatus(to)}>
              Mark {words(to)}
            </button>
          ))}
        </div>
      )}

      {active.length > 0 && (
        <ul className="assigned">
          {active.map((a) => (
            <li key={a.id}>
              <span className="assigned__name">{teamName(a.team_id)}</span>
              <span className="pill pill--neutral">{a.role}</span>
              <button type="button" className="btn btn--small btn--danger" onClick={() => onRecall(a.team_id)}>
                Recall
              </button>
            </li>
          ))}
        </ul>
      )}

      {active.length === 0 && (
        <>
          <h4 className="subhead">Suggested</h4>
          <SuggestionList
            suggestions={suggestions}
            canAssign={(teamId) => canAssign(state, incident, state.teams.find((t) => t.id === teamId)!, now).ok}
            onAssign={(teamId) => setPending({ team: state.teams.find((t) => t.id === teamId)!, backup: false })}
          />
          <p className="hint">The system suggests; you decide and confirm.</p>
        </>
      )}

      <details className="more">
        <summary>{active.length > 0 ? 'Add a backup team' : 'All teams'}</summary>
        <ul className="teamlist">
          {state.teams.map((team) => {
            // Opening "Add a backup team" and confirming is the explicit backup step.
            const asBackup = active.length > 0;
            const check = canAssign(state, incident, team, now, { backup: asBackup });
            return (
              <li key={team.id} className={check.ok ? 'teamlist__row' : 'teamlist__row teamlist__row--blocked'}>
                <span className="teamlist__name">{team.name}</span>
                <span className="teamlist__why">{check.ok ? words(team.status) : check.reasons[0]}</span>
                <button
                  type="button"
                  className="btn btn--small"
                  disabled={!check.ok}
                  title={check.reasons.join('\n')}
                  onClick={() => setPending({ team, backup: asBackup })}
                >
                  {asBackup ? 'Backup' : 'Assign'}
                </button>
              </li>
            );
          })}
        </ul>
      </details>

      {pending && (
        <AssignDialog
          incident={incident}
          team={pending.team}
          backup={pending.backup}
          safetyNotes={canAssign(state, incident, pending.team, now, { backup: pending.backup }).safetyNotes}
          onCancel={() => setPending(null)}
          onConfirm={() => {
            onAssign(pending.team.id, pending.backup);
            setPending(null);
          }}
        />
      )}
    </section>
  );
}
