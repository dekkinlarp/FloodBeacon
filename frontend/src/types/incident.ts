import type { AccessType, IncidentSource, IncidentStatus, Language, Need, Severity } from './enums';
import type { LatLon } from './location';

/** A person or household needing help. Health details live in `Health`, not here. */
export interface Incident {
  id: string;
  created_at: string; // ISO 8601 with offset
  updated_at: string;
  status: IncidentStatus;
  severity: Severity;
  access_type: AccessType;
  district: string; // Bangkok district (khet), English name
  location: LatLon;
  address_note: string;
  needs: Need[];
  people_count: number;
  reporter_language: Language;
  contact_phone: string | null;
  last_contact_at: string | null;
  source: IncidentSource;
  /** Raw text as received (SMS etc). Shown next to AI-extracted fields. */
  original_message: string | null;
  /** True when fields were extracted by Gemini from `original_message`. */
  ai_extracted: boolean;
  verified_by_human: boolean;
}
