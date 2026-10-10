import type { Assignment, Team, TeamStatus } from '../types';
import { TEAM_TRANSITIONS } from '../logic/dispatch';
import { formatHours } from '../logic/contactBadge';
import { BLOCK_ASSIGNMENT_HOURS, SUGGEST_REST_HOURS, checkInState, fatigue, formatCheckInAge } from '../logic/safety';
import { teamViewHref } from '../logic/route';

interface Props {
  teams: readonly Team[];
  assignments: readonly Assignment[];
  now: Date;
  /** Top suggestion for the selected incident, highlighted. */
  bestTeamId?: string | null;
  /** Teams that cannot go to the selected incident, with reasons; dimmed. */
  excluded?: ReadonlyMap<string, readonly string[]>;
  onRecall: (teamId: string) => void;
  onStatus: (teamId: string, to: TeamStatus) => void;
  /** Dispatcher logs a check-in received by radio/phone. */
  onCheckIn: (teamId: string) => void;
}

const words = (s: string) => s.replace(/_/g, ' ');

/** One row per team: status, job, fatigue, check-in, actions. */
export function TeamBoard({ teams, assignments, now, bestTeamId = null, excluded, onRecall, onStatus, onCheckIn }: Props) {
  return (
    <section className="board" aria-label="Teams">
      <h2 className="panel-title">
        Teams{' '}
        <span className="panel-title__count">
          {teams.filter((t) => t.status === 'available').length} free · {teams.length} total
        </span>
      </h2>
      <div className="board__scroll">
        <table className="board__table">
          <thead>
            <tr>
              <th>Team</th>
              <th>Status · job</th>
              <th>Duty · check-in</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {teams.map((team) => {
              const job = assignments.find((a) => a.team_id === team.id && a.ended_at === null);
              const checkIn = checkInState(team, now);
              const tired = fatigue(team, now);
              const cantGo = excluded?.get(team.id);
              const best = team.id === bestTeamId;
              const cls = ['trow', best && 'trow--best', cantGo && 'trow--dim', checkIn.missed && 'trow--missed']
                .filter(Boolean)
                .join(' ');
              return (
                <tr key={team.id} className={cls}>
                  <td>
                    <a
                      className="trow__name"
                      href={teamViewHref(team.id)}
                      title={`Team view\nSkills: ${team.skills.map(words).join(', ') || 'none'}\nEquipment: ${team.equipment.join(', ') || 'none'}`}
                    >
                      {team.name}
                    </a>
                    <span className="trow__sub">
                      {words(team.vehicle)} · {team.members_count}p
                    </span>
                    {best && <span className="tag tag--accent">Best</span>}
                  </td>
                  <td className="trow__job">
                    <span className={`pill pill--team-${team.status}`}>{words(team.status)}</span>
                    {job ? (
                      <span className="trow__sub">
                        {' '}
                        <span className="mono trow__inc">{job.incident_id}</span>
                        {job.role === 'backup' && ' backup'}
                      </span>
                    ) : (
                      cantGo && (
                        <span className="trow__why" title={cantGo.join('\n')}>
                          {cantGo[0]}
                        </span>
                      )
                    )}
                  </td>
                  <td className="trow__duty">
                    <span
                      className={`duty duty--${tired.level}`}
                      title={`Suggest rest at ${SUGGEST_REST_HOURS} h; no new assignments above ${BLOCK_ASSIGNMENT_HOURS} h`}
                    >
                      <span
                        className="duty__bar"
                        role="meter"
                        aria-label="Hours on duty"
                        aria-valuemin={0}
                        aria-valuemax={BLOCK_ASSIGNMENT_HOURS}
                        aria-valuenow={Math.round(tired.hours * 10) / 10}
                      >
                        <span style={{ width: `${tired.fraction * 100}%` }} />
                      </span>
                      <span className="mono">{team.on_duty_since ? formatHours(tired.hours) : 'off'}</span>
                    </span>
                    <span className={checkIn.missed ? 'trow__checkin trow__checkin--missed' : 'trow__checkin'}>
                      {checkIn.missed && <span className="tag tag--danger">Missed</span>}
                      <span className="mono">check-in {formatCheckInAge(checkIn.minutesSince)}</span>
                    </span>
                  </td>
                  <td className="trow__actions">
                    {team.status !== 'off_duty' && (
                      <button type="button" className="btn btn--tiny" onClick={() => onCheckIn(team.id)} title="Log a check-in received by radio">
                        Check-in
                      </button>
                    )}
                    {job && (
                      <button type="button" className="btn btn--tiny btn--danger" onClick={() => onRecall(team.id)}>
                        Recall
                      </button>
                    )}
                    {TEAM_TRANSITIONS[team.status].length > 0 && (
                      <select
                        className="btn btn--tiny"
                        aria-label={`Set status for ${team.name}`}
                        value=""
                        onChange={(e) => e.target.value && onStatus(team.id, e.target.value as TeamStatus)}
                      >
                        <option value="">Set…</option>
                        {TEAM_TRANSITIONS[team.status].map((to) => (
                          <option key={to} value={to}>
                            {words(to)}
                          </option>
                        ))}
                      </select>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
