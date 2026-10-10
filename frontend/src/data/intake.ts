/** Same-origin proxy. Operator credentials stay in memory, never in localStorage or VITE_* env. */
export interface IntakeAddress {
  house_number: string | null; street: string | null; unit: string | null;
  city: string | null; region: string | null; country: string | null;
  postal_code: string | null; telephone_area_code: string | null;
  landmark: string | null; location_detail: string | null; unavailable_fields: string[];
}
export interface IntakeSituation {
  summary: string; people_count: number | null; address: IntakeAddress;
  reporter_relationship: string; reported_hazards: string[]; assistance_needs: string[];
  reported_resolution: boolean;
  evidence: { field: string; message_sid: string; quote: string }[];
}
export interface IntakeIncident {
  id: string; conversation_id: string; version: number;
  created_at: number; updated_at: number;
  verification_status: string; response_status: string; operational_priority: string;
  latitude: number | null; longitude: number | null; location_status: string;
  location_source: string | null; needs_review: boolean;
  report: { report_type: string; situations: IntakeSituation[]; conflicts: string[]; missing_information: string[] };
}
export interface IntakeDetail extends IntakeIncident {
  messages: { sid: string; body: string; received_at: number; status: string; error: string | null }[];
}
export type IntakePatch = {
  expected_version: number; reason: string;
  verification_status?: string; response_status?: string; operational_priority?: string;
};

export async function intakeRequest<T>(key: string, path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/intake${path}`, {
    ...options, cache: 'no-store',
    headers: { ...options.headers, Accept: 'application/json', Authorization: `Bearer ${key}`,
      ...(options.body ? { 'Content-Type': 'application/json' } : {}) },
  });
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) throw new Error('Invalid operator key. Reconnect with OPERATOR_API_KEY from twillio/.env.');
    if (response.status === 409) throw new Error('This report changed. Refresh and review it before saving again.');
    throw new Error(`Intake API returned ${response.status}. Check that the Python API is running on port 8000.`);
  }
  return await response.json() as T;
}

export function hasMapLocation(i: IntakeIncident): boolean {
  return i.report.situations.length === 1 && typeof i.latitude === 'number' && Number.isFinite(i.latitude)
    && typeof i.longitude === 'number' && Number.isFinite(i.longitude)
    && Math.abs(i.latitude) <= 90 && Math.abs(i.longitude) <= 180;
}

export function addressLabel(a: IntakeAddress): string {
  return [[a.house_number, a.street].filter(Boolean).join(' '), a.unit ? `Unit ${a.unit}` : '',
    a.city, a.region, a.postal_code, a.country, a.landmark].filter(Boolean).join(', ') || 'Location not yet reported';
}

/** Canonical case IDs prevent follow-up message versions from appearing as extra rescues. */
export function normalizeIncidents(rows: IntakeIncident[]): IntakeIncident[] {
  if (!Array.isArray(rows)) throw new Error('Intake API returned an invalid incident list.');
  const byId = new Map<string, IntakeIncident>();
  for (const row of rows) {
    if (!row || typeof row.id !== 'string' || !Number.isFinite(row.version)
      || !Number.isFinite(row.updated_at) || !Array.isArray(row.report?.situations)) {
      throw new Error('Intake API returned an invalid incident record.');
    }
    const old = byId.get(row.id);
    if (!old || row.version > old.version) byId.set(row.id, row);
  }
  return [...byId.values()].sort((a, b) => b.updated_at - a.updated_at || a.id.localeCompare(b.id));
}
