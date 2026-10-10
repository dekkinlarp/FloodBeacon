import type { TeamSuggestion } from '../logic/suggest';

interface Props {
  suggestions: readonly TeamSuggestion[];
  /** Whether "Assign" may be offered for this team right now (canAssign). */
  canAssign: (teamId: string) => boolean;
  onAssign: (teamId: string) => void;
}

/** Ranked suggestions. The dispatcher still chooses and confirms (no auto-assign). */
export function SuggestionList({ suggestions, canAssign, onAssign }: Props) {
  if (suggestions.length === 0) {
    return <p className="empty">No available team fits. Dimmed rows on the team board show why.</p>;
  }
  return (
    <ol className="suggest">
      {suggestions.map((s, i) => (
        <li key={s.team.id} className={i === 0 ? 'suggest__row suggest__row--best' : 'suggest__row'}>
          <span className="suggest__rank">{i + 1}</span>
          <span className="suggest__main">
            <span className="suggest__name">
              {s.team.name}
              <span className="suggest__score">{s.score}</span>
            </span>
            <span className="suggest__why">{s.reasons.join(' · ')}</span>
          </span>
          <button
            type="button"
            className="btn btn--small btn--primary"
            disabled={!canAssign(s.team.id)}
            onClick={() => onAssign(s.team.id)}
          >
            Assign
          </button>
        </li>
      ))}
    </ol>
  );
}
