import { useState, type FormEvent } from 'react';
import type { FeedbackOutcome } from '../types';
import type { FeedbackInput } from '../logic/feedback';
import { MAX_BLOCKED_ROUTES_CHARS, MAX_WATER_DEPTH_CM, validateFeedbackInput } from '../logic/feedback';

const OUTCOME_LABELS: Record<FeedbackOutcome, string> = {
  evacuated: 'Evacuated',
  supplied: 'Supplied (food, water, medicine)',
  referred_1669: 'Referred to 1669',
  no_one_found: 'No one found',
  could_not_reach: 'Could not reach',
};

interface Props {
  teamId: string;
  outcomes: readonly FeedbackOutcome[];
  /** Resolves to the reasons it was refused, or null when saved. */
  onSubmit: (input: FeedbackInput) => Promise<string[] | null>;
  onCancel: () => void;
}

/** Report from the field. Returns to the caller; nothing is sent until Submit. */
export function FieldFeedbackForm({ teamId, outcomes, onSubmit, onCancel }: Props) {
  const [depth, setDepth] = useState('');
  const [routeWorked, setRouteWorked] = useState<boolean | null>(null);
  const [blocked, setBlocked] = useState('');
  const [people, setPeople] = useState('0');
  const [outcome, setOutcome] = useState<FeedbackOutcome>(outcomes[0]!);
  const [photoRef, setPhotoRef] = useState<string | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [sending, setSending] = useState(false);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (routeWorked === null) {
      setErrors(['Say whether the route worked.']);
      return;
    }
    const input: FeedbackInput = {
      teamId,
      water_depth_cm: depth.trim() === '' ? null : Number(depth),
      route_worked: routeWorked,
      blocked_routes: blocked,
      people_helped: people.trim() === '' ? 0 : Number(people),
      outcome,
      photo_ref: photoRef,
    };
    const problems = validateFeedbackInput(input);
    if (problems.length > 0) {
      setErrors(problems);
      return;
    }
    setSending(true);
    onSubmit(input)
      .then((reasons) => setErrors(reasons ?? []))
      .finally(() => setSending(false));
  }

  return (
    <form className="feedback-form" onSubmit={submit} noValidate>
      <h2>Field feedback</h2>
      {errors.length > 0 && (
        <ul className="form-errors" role="alert">
          {errors.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
      )}

      <label className="field">
        <span>Outcome</span>
        <select value={outcome} onChange={(e) => setOutcome(e.target.value as FeedbackOutcome)}>
          {outcomes.map((o) => (
            <option key={o} value={o}>
              {OUTCOME_LABELS[o]}
            </option>
          ))}
        </select>
      </label>

      <label className="field">
        <span>Water depth at the site (cm, optional)</span>
        <input
          type="number"
          inputMode="numeric"
          min={0}
          max={MAX_WATER_DEPTH_CM}
          value={depth}
          onChange={(e) => setDepth(e.target.value)}
        />
      </label>

      <fieldset className="field">
        <legend>Did the route work?</legend>
        <label className="choice">
          <input type="radio" name="route" checked={routeWorked === true} onChange={() => setRouteWorked(true)} /> Yes
        </label>
        <label className="choice">
          <input type="radio" name="route" checked={routeWorked === false} onChange={() => setRouteWorked(false)} /> No
        </label>
      </fieldset>

      <label className="field">
        <span>Blocked roads or bridges</span>
        <textarea
          rows={3}
          maxLength={MAX_BLOCKED_ROUTES_CHARS}
          value={blocked}
          onChange={(e) => setBlocked(e.target.value)}
          placeholder="e.g. Soi 20 bridge under water"
        />
      </label>

      <label className="field">
        <span>People helped</span>
        <input type="number" inputMode="numeric" min={0} step={1} value={people} onChange={(e) => setPeople(e.target.value)} />
      </label>

      <label className="field">
        <span>Photo (optional)</span>
        <input
          type="file"
          accept="image/*"
          capture="environment"
          onChange={(e) => setPhotoRef(e.target.files?.[0]?.name ?? null)}
        />
        <small className="muted">Only the file name is saved for now; upload comes later.</small>
      </label>

      <div className="feedback-form__actions">
        <button type="button" className="btn btn--big" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="btn btn--primary btn--big" disabled={sending}>
          {sending ? 'Sending…' : 'Submit feedback'}
        </button>
      </div>
    </form>
  );
}
