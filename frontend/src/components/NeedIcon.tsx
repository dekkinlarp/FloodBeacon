import type { Need } from '../types';

const LABELS: Record<Need, string> = {
  rescue: 'Rescue',
  evacuation: 'Evacuation',
  medical: 'Medical',
  medication: 'Medication',
  food_water: 'Food and water',
  power: 'Power',
};

export function needLabel(need: Need): string {
  return LABELS[need];
}

/** Hand-drawn 24×24 line icons; colour comes from `currentColor`. */
export function NeedIcon({ need, size = 16 }: { need: Need | null; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.4}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {need === 'rescue' && (
        <>
          <circle cx="12" cy="12" r="8.5" />
          <circle cx="12" cy="12" r="3.5" />
          <path d="M6 6l3.5 3.5M18 6l-3.5 3.5M6 18l3.5-3.5M18 18l-3.5-3.5" />
        </>
      )}
      {need === 'medical' && <path d="M12 4v16M4 12h16" strokeWidth={3.5} />}
      {need === 'evacuation' && (
        <>
          <path d="M4 20V9l6-5 6 5" />
          <path d="M11 15h10M17 11l4 4-4 4" />
        </>
      )}
      {need === 'medication' && (
        <>
          <rect x="3" y="8.5" width="18" height="7" rx="3.5" transform="rotate(-40 12 12)" />
          <path d="M9.7 9.3l4.6 5.4" />
        </>
      )}
      {need === 'food_water' && <path d="M12 3c-3 4.5-6 7.8-6 11a6 6 0 0 0 12 0c0-3.2-3-6.5-6-11z" />}
      {need === 'power' && <path d="M13 2L5 14h6l-1 8 8-12h-6z" />}
      {need === null && <circle cx="12" cy="12" r="3" />}
    </svg>
  );
}
