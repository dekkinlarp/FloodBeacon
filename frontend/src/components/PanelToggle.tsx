interface Props {
  /** Panel name for the accessible label, e.g. "queue". */
  label: string;
  expanded: boolean;
  /** Id of the region this button shows and hides. */
  controls: string;
  /** Direction the panel collapses toward; the chevron points that way while expanded. */
  toward: 'left' | 'down';
  onToggle: () => void;
}

/** Round chevron button that collapses or expands a console panel. Hidden on phones. */
export function PanelToggle({ label, expanded, controls, toward, onToggle }: Props) {
  return (
    <button
      type="button"
      className={`panel-toggle panel-toggle--${toward}`}
      aria-expanded={expanded}
      aria-controls={controls}
      aria-label={`${expanded ? 'Collapse' : 'Expand'} ${label}`}
      title={`${expanded ? 'Collapse' : 'Expand'} ${label}`}
      onClick={onToggle}
    >
      <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
        <path d="M8.5 3.5 5 7l3.5 3.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
  );
}
