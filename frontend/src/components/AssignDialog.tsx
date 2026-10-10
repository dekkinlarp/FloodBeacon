import { useEffect, useRef } from 'react';
import type { Incident, Team } from '../types';

interface Props {
  incident: Incident;
  team: Team;
  backup: boolean;
  safetyNotes: readonly string[];
  onConfirm: () => void;
  onCancel: () => void;
}

const words = (s: string) => s.replace(/_/g, ' ');

/** Confirm step before any assignment. Safety notes warn but never block. */
export function AssignDialog({ incident, team, backup, safetyNotes, onConfirm, onCancel }: Props) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current!;
    dialog.showModal();
    return () => dialog.close();
  }, []);

  return (
    <dialog ref={ref} className="assign-dialog" aria-labelledby="assign-dialog-title" onCancel={onCancel}>
      <h2 id="assign-dialog-title">{backup ? 'Add backup team' : 'Assign team'}</h2>
      <dl className="fields">
        <dt>Team</dt>
        <dd>
          {team.name} · {words(team.vehicle)} · {team.members_count} people
        </dd>
        <dt>Incident</dt>
        <dd>
          {incident.id} · {incident.district}
        </dd>
        <dt>Severity</dt>
        <dd>{incident.severity}</dd>
        <dt>Access</dt>
        <dd>{words(incident.access_type)}</dd>
        <dt>Role</dt>
        <dd>{backup ? 'backup' : 'primary'}</dd>
      </dl>
      <h3>Safety notes</h3>
      {safetyNotes.length === 0 ? (
        <p className="empty">None.</p>
      ) : (
        <ul className="safety-notes">
          {safetyNotes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
      <div className="assign-dialog__actions">
        <button type="button" className="btn" onClick={onCancel}>
          Cancel
        </button>
        <button type="button" className="btn btn--primary" onClick={onConfirm} autoFocus>
          Confirm assignment
        </button>
      </div>
    </dialog>
  );
}
