import type { IncidentStatus, Severity } from '../types';
import { SEVERITIES } from '../types';

/** Fill colour per severity: critical red, high orange, medium yellow, low green. */
export const SEVERITY_COLOURS: Record<Severity, string> = {
  critical: '#e5484d',
  high: '#f76b15',
  medium: '#f5c518',
  low: '#30a46c',
};

export const RESOLVED_COLOUR = '#6b6b6b';

export interface MarkerStyle {
  fill: string;
  /** Icon/text colour that stays readable on `fill`. */
  ink: string;
}

/** Resolved incidents are grey whatever their severity. */
export function markerStyle(severity: Severity, status: IncidentStatus): MarkerStyle {
  if (status === 'resolved') return { fill: RESOLVED_COLOUR, ink: '#ffffff' };
  return { fill: SEVERITY_COLOURS[severity], ink: severity === 'medium' ? '#1a1a1a' : '#ffffff' };
}

/** 0 = most urgent (critical). */
export function severityRank(severity: Severity): number {
  return SEVERITIES.indexOf(severity);
}
