import { afterEach, describe, expect, it, vi } from 'vitest';
import { addressLabel, hasMapLocation, intakeRequest, normalizeIncidents, type IntakeIncident } from '../../src/data/intake';
const fixture = (changes: Partial<IntakeIncident> = {}): IntakeIncident => ({
  id: 'case-1', conversation_id: 'conversation-1', version: 1, created_at: 10, updated_at: 10,
  verification_status: 'unverified', response_status: 'new', operational_priority: 'unassigned',
  latitude: null, longitude: null, location_status: 'unresolved', location_source: null, needs_review: true,
  report: { report_type: 'rescue_request', conflicts: [], missing_information: [], situations: [{
    summary: 'Help needed', people_count: null, reported_hazards: [], assistance_needs: [],
    reporter_relationship: 'unknown', reported_resolution: false, evidence: [],
    address: { house_number: null, street: null, unit: null, city: null, region: null, country: null,
      postal_code: null, telephone_area_code: null, landmark: null, location_detail: null, unavailable_fields: [] },
  }] }, ...changes,
});
afterEach(() => vi.unstubAllGlobals());
describe('live intake integration', () => {
  it('retains unknown counts and addresses instead of making up coordinates', () => {
    const row = fixture();
    expect(hasMapLocation(row)).toBe(false);
    expect(normalizeIncidents([row])[0]?.report.situations[0]?.people_count).toBeNull();
    expect(addressLabel(row.report.situations[0]!.address)).toBe('Location not yet reported');
  });
  it('keeps latest canonical case version rather than duplicating follow-ups', () => {
    expect(normalizeIncidents([fixture(), fixture({ version: 2, updated_at: 20 })])).toEqual([fixture({ version: 2, updated_at: 20 })]);
  });
  it('maps valid global coordinates, including zero, but never multi-location cases', () => {
    expect(hasMapLocation(fixture({ latitude: 49, longitude: -122 }))).toBe(true);
    expect(hasMapLocation(fixture({ latitude: 0, longitude: 0 }))).toBe(true);
    expect(hasMapLocation(fixture({ latitude: 91, longitude: -122 }))).toBe(false);
    expect(hasMapLocation(fixture({ latitude: NaN, longitude: -122 }))).toBe(false);
    const multi = fixture({ latitude: 49, longitude: -122 });
    multi.report.situations.push(multi.report.situations[0]!);
    expect(hasMapLocation(multi)).toBe(false);
  });
  it('formats the explicitly supplied address', () => {
    const a = fixture().report.situations[0]!.address;
    expect(addressLabel({ ...a, house_number: '42B', street: 'Example Street', city: 'Abbotsford' }))
      .toBe('42B Example Street, Abbotsford');
  });
  it('passes bearer auth to same-origin proxy and preserves nested JSON', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([fixture()])));
    vi.stubGlobal('fetch', fetch);
    expect(await intakeRequest('test-secret', '/incidents')).toEqual([fixture()]);
    expect(fetch.mock.calls[0]?.[0]).toBe('/intake/incidents');
    expect(fetch.mock.calls[0]?.[1].headers.Authorization).toBe('Bearer test-secret');
  });
  it('exposes authentication and conflict failures without falling back to fake data', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 401 })));
    await expect(intakeRequest('wrong', '/incidents')).rejects.toThrow('Invalid operator key');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 409 })));
    await expect(intakeRequest('key', '/incidents/a', { method: 'PATCH' })).rejects.toThrow('report changed');
  });
});
