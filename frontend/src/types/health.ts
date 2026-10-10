import type { MedicalNeed, MobilityLevel, Severity } from './enums';

export interface VulnerableCounts {
  elderly: number;
  children: number;
  pregnant: number;
  disabled: number;
}

/**
 * Sensitive. Map shows only `priority` colour + need icon; full record only in
 * the incident card. Never log to the console.
 */
export interface Health {
  incident_id: string;
  priority: Severity;
  medical_needs: MedicalNeed[];
  mobility: MobilityLevel;
  /** How many people in each vulnerable group are at the incident. */
  vulnerable: VulnerableCounts;
  /** Free-text descriptions, e.g. "cut on lower leg, bleeding". */
  injuries: string[];
  /** Free text, e.g. "oxygen cylinder ~6 h". Null when unknown. */
  supplies_left: string | null;
  notes: string;
  /** True when fields came from Gemini parsing of the incident's original message. */
  ai_extracted: boolean;
  verified_by_human: boolean;
  updated_at: string;
}
