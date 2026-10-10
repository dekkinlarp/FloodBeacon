import { useState } from 'react';
import type { FeedbackOutcome, IncidentStatus, RoutePlan } from '../types';
import { activeAssignmentForTeam, canTransitionIncident, describeLegs, routeFor, safetyNotes } from '../logic/dispatch';
import { allowedOutcomes, OUTCOME_STATUS } from '../logic/feedback';
import { checkInState, equipmentCheck, fatigue, formatCheckInAge } from '../logic/safety';
import { emergencyReminders } from '../logic/emergencyReminder';
import { formatHours } from '../logic/contactBadge';
import { teamActor, useDispatchStore } from '../state/DispatchStore';
import { useNow } from '../state/Clock';
import { needLabel } from '../components/NeedIcon';
import { FieldFeedbackForm } from '../components/FieldFeedbackForm';

const words = (s: string) => s.replace(/_/g, ' ');

/**
 * One team's current job, for a phone in the field. Shows no health details
 * beyond the 1669/1784 reminder (CLAUDE.md rule 7).
 */
export function TeamView({ teamId }: { teamId: string }) {
  const now = useNow();
  const store = useDispatchStore();
  const [feedbackFor, setFeedbackFor] = useState<'resolved' | 'could_not_reach' | null>(null);
  const [sent, setSent] = useState<string | null>(null);
  const { teams, incidents, health, feedback } = store.data;
  const team = teams.find((t) => t.id === teamId);

  if (!team) {
    return (
      <div className="team-view">
        <a href="#/">← Dispatch</a>
        <p>Unknown team {teamId}.</p>
      </div>
    );
  }

  const assignment = activeAssignmentForTeam(store.data, team.id);
  const incident = assignment ? incidents.find((i) => i.id === assignment.incident_id) : undefined;
  const checkIn = checkInState(team, now);
  const tired = fatigue(team, now);

  const can = (to: IncidentStatus) => !!incident && canTransitionIncident(incident.status, to);
  const outcomesFor = (target: 'resolved' | 'could_not_reach'): FeedbackOutcome[] =>
    incident ? allowedOutcomes(incident.status).filter((o) => OUTCOME_STATUS[o] === target) : [];

  return (
    <div className="team-view">
      <header className="team-view__header">
        <a href="#/" className="team-view__back">
          ← Dispatch
        </a>
        <h1>{team.name}</h1>
        <p>
          {words(team.status)} · {words(team.vehicle)} · {team.on_duty_since ? `${formatHours(tired.hours)} on duty` : 'off duty'}
          {tired.level === 'rest' && ' · rest soon'}
          {tired.level === 'block' && ' · over the duty limit'}
        </p>
        <div className={`team-view__checkin${checkIn.missed ? ' team-view__checkin--missed' : ''}`}>
          <span>
            {checkIn.missed ? 'Check-in overdue' : 'Last check-in'}:{' '}
            {formatCheckInAge(checkIn.minutesSince)}
          </span>
          {team.status !== 'off_duty' && (
            <button type="button" className="btn btn--big" onClick={() => store.checkIn(team.id, teamActor(team.id))}>
              Check in now
            </button>
          )}
        </div>
      </header>

      {store.error && (
        <div className="alert alert--error" role="alert">
          {store.error.join(' ')}{' '}
          <button type="button" className="btn btn--small" onClick={store.clearError}>
            OK
          </button>
        </div>
      )}
      {sent && (
        <p className="alert alert--ok" role="status">
          {sent}
        </p>
      )}

      {!incident ? (
        <p className="team-view__empty">No current assignment. Wait for dispatch.</p>
      ) : (
        <>
          {emergencyReminders(incident, health.find((h) => h.incident_id === incident.id)).map((r) => (
            <p key={r.number} className="reminder" role="alert">
              <span className="reminder__number">Call {r.number}</span>
              <span>{r.label.replace(/^Call \d+ — /, '')}</span>
            </p>
          ))}

          <section className="team-view__section">
            <h2>Destination</h2>
            <p className="team-view__dest">
              <strong>{incident.id}</strong> · {incident.district}
            </p>
            <p>{incident.address_note}</p>
            <p className="muted">
              {incident.location.lat.toFixed(5)}, {incident.location.lon.toFixed(5)}
            </p>
            <p>
              {incident.people_count} people · {incident.needs.map(needLabel).join(', ')} · status{' '}
              <strong>{words(incident.status)}</strong>
              {assignment?.role === 'backup' && ' · you are backup'}
            </p>
            {incident.ai_extracted && (
              <div className={`ai-flag${incident.verified_by_human ? '' : ' ai-flag--unverified'}`}>
                Details extracted by AI. verified_by_human: {incident.verified_by_human ? 'yes' : 'NO'}
                {incident.original_message && <blockquote className="original-message">{incident.original_message}</blockquote>}
              </div>
            )}
          </section>

          <section className="team-view__section">
            <h2>Route</h2>
            {store.data.alerts
              .filter((a) => a.incident_id === incident.id && a.team_id === team.id)
              .map((a) => (
                <p key={a.id} className="alert alert--route" role="alert">
                  {a.message}
                </p>
              ))}
            <RouteSummary plan={routeFor(store.data, team.id, incident.id)} access={incident.access_type} />
            {feedback
              .filter((f) => f.incident_id === incident.id && f.blocked_routes)
              .map((f) => (
                <p key={f.id} className="team-view__blocked">
                  Reported blocked ({f.team_id}): {f.blocked_routes}
                </p>
              ))}
          </section>

          <section className="team-view__section">
            <h2>Safety</h2>
            {(() => {
              const notes = safetyNotes(incident, team, now);
              return notes.length ? (
                <ul className="safety-notes">
                  {notes.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              ) : (
                <p className="muted">No safety notes.</p>
              );
            })()}
            <h3>Required equipment</h3>
            <ul className="equipment">
              {equipmentCheck(incident, team).map(({ item, carried }) => (
                <li key={item} className={carried ? 'equipment--ok' : 'equipment--missing'}>
                  {item}: {carried ? 'carried' : 'NOT on team list — check before leaving'}
                </li>
              ))}
              {equipmentCheck(incident, team).length === 0 && <li className="muted">Nothing specific.</li>}
            </ul>
          </section>

          {feedbackFor ? (
            <FieldFeedbackForm
              teamId={team.id}
              outcomes={outcomesFor(feedbackFor)}
              onCancel={() => setFeedbackFor(null)}
              onSubmit={async (input) => {
                const r = await store.submitFeedback(input);
                if (!r.ok) return r.reasons;
                setFeedbackFor(null);
                setSent(`Feedback sent for ${incident.id}. Incident is now ${words(OUTCOME_STATUS[input.outcome])}.`);
                return null;
              }}
            />
          ) : (
            <section className="team-view__section team-view__status">
              <h2>Update status</h2>
              <button type="button" className="btn btn--big" disabled={!can('en_route')} onClick={() => store.fieldReport(team.id, 'en_route')}>
                En route
              </button>
              <button type="button" className="btn btn--big" disabled={!can('on_scene')} onClick={() => store.fieldReport(team.id, 'on_scene')}>
                On scene
              </button>
              <button
                type="button"
                className="btn btn--big btn--danger"
                disabled={outcomesFor('could_not_reach').length === 0}
                onClick={() => {
                  setSent(null);
                  setFeedbackFor('could_not_reach');
                }}
              >
                Could not reach…
              </button>
              <button
                type="button"
                className="btn btn--big btn--primary"
                disabled={outcomesFor('resolved').length === 0}
                onClick={() => {
                  setSent(null);
                  setFeedbackFor('resolved');
                }}
              >
                Resolved…
              </button>
              <p className="muted">"Could not reach" and "Resolved" ask for field feedback first.</p>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function RouteSummary({ plan, access }: { plan: RoutePlan | null; access: string }) {
  if (!plan) return <p>Travel time unknown · access {words(access)}</p>;
  const total = plan.legs.reduce((sum, l) => sum + l.minutes, 0);
  return (
    <>
      <p>
        About {Math.round(total)} min: <strong>{describeLegs(plan.legs)}</strong> · access {words(access)}
      </p>
      {plan.reason && <p>Changed because: {plan.reason}</p>}
      <p className="muted">Estimate only. Detailed routes will come from the routing team (Person 2).</p>
    </>
  );
}
