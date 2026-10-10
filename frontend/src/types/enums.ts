// Enum values exactly as listed in CLAUDE.md. Arrays are exported so runtime
// validation and the SQL schema can use the same lists.

export const INCIDENT_STATUSES = [
  'new',
  'verified',
  'assigned',
  'en_route',
  'on_scene',
  'resolved',
  'could_not_reach',
  'cancelled',
] as const;
export type IncidentStatus = (typeof INCIDENT_STATUSES)[number];

export const TEAM_STATUSES = [
  'available',
  'en_route',
  'on_scene',
  'returning',
  'resting',
  'off_duty',
] as const;
export type TeamStatus = (typeof TEAM_STATUSES)[number];

export const SEVERITIES = ['critical', 'high', 'medium', 'low'] as const;
export type Severity = (typeof SEVERITIES)[number];

export const ACCESS_TYPES = ['truck', 'boat_only', 'walk_only'] as const;
export type AccessType = (typeof ACCESS_TYPES)[number];

// Not defined in CLAUDE.md — added in Session 1, open for review (PLAN.md Q4).

export const NEEDS = [
  'rescue',
  'evacuation',
  'medical',
  'medication',
  'food_water',
  'power',
] as const;
export type Need = (typeof NEEDS)[number];

export const MEDICAL_NEEDS = [
  'dialysis',
  'oxygen',
  'insulin',
  'pregnancy',
  'injury',
  'mobility',
] as const;
export type MedicalNeed = (typeof MEDICAL_NEEDS)[number];

export const MOBILITY_LEVELS = ['independent', 'assisted', 'bedridden'] as const;
export type MobilityLevel = (typeof MOBILITY_LEVELS)[number];

export const INCIDENT_SOURCES = ['sms', 'phone', 'field', 'dispatcher'] as const;
export type IncidentSource = (typeof INCIDENT_SOURCES)[number];

export const VEHICLES = ['truck', 'flat_boat', 'kayak', 'on_foot'] as const;
export type Vehicle = (typeof VEHICLES)[number];

export const SKILLS = ['first_aid', 'boat_operator', 'swimmer'] as const;
export type Skill = (typeof SKILLS)[number];

export const LANGUAGES = ['thai', 'english', 'burmese'] as const;
export type Language = (typeof LANGUAGES)[number];

export const ASSIGNMENT_END_REASONS = [
  'resolved',
  'reassigned',
  'could_not_reach',
  'cancelled',
  'recalled',
] as const;
export type AssignmentEndReason = (typeof ASSIGNMENT_END_REASONS)[number];

/** One primary team per incident; backups only when added explicitly. */
export const ASSIGNMENT_ROLES = ['primary', 'backup'] as const;
export type AssignmentRole = (typeof ASSIGNMENT_ROLES)[number];

export const EVENT_ENTITY_TYPES = ['incident', 'health', 'team', 'assignment', 'feedback'] as const;
export type EventEntityType = (typeof EVENT_ENTITY_TYPES)[number];

export const EVENT_TYPES = [
  'created',
  'updated',
  'status_changed',
  'verified',
  'assigned',
  'unassigned',
  'recalled',
  'checked_in',
] as const;
export type EventType = (typeof EVENT_TYPES)[number];

/** What happened at the incident, reported by the field team. */
export const FEEDBACK_OUTCOMES = [
  'evacuated',
  'supplied',
  'referred_1669',
  'no_one_found',
  'could_not_reach',
] as const;
export type FeedbackOutcome = (typeof FEEDBACK_OUTCOMES)[number];
