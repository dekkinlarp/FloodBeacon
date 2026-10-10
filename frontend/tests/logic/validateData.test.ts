import { describe, expect, it } from 'vitest';
import incidents from '../../data/fake/incidents.json';
import health from '../../data/fake/health.json';
import teams from '../../data/fake/teams.json';
import {
  validateDataset,
  validateHealth,
  validateIncident,
  validateTeam,
} from '../../src/logic/validateData';

const firstIncident = incidents[0]!;
const firstTeam = teams[0]!;

describe('fake data matches the types', () => {
  it('has no validation errors', () => {
    expect(validateDataset({ incidents, health, teams })).toEqual([]);
  });
});

describe('fake data meets the Session 1 brief', () => {
  it('has 20 incidents across at least 8 districts', () => {
    expect(incidents).toHaveLength(20);
    expect(new Set(incidents.map((i) => i.district)).size).toBeGreaterThanOrEqual(8);
  });

  it('mixes severities, needs and access types', () => {
    expect(new Set(incidents.map((i) => i.severity)).size).toBe(4);
    expect(new Set(incidents.map((i) => i.access_type)).size).toBe(3);
    expect(new Set(incidents.flatMap((i) => i.needs)).size).toBeGreaterThanOrEqual(5);
  });

  it('has at least 2 critical medical cases, one a dialysis patient', () => {
    const critical = health.filter((h) => {
      const inc = incidents.find((i) => i.id === h.incident_id);
      return h.priority === 'critical' && inc?.severity === 'critical';
    });
    expect(critical.length).toBeGreaterThanOrEqual(2);
    expect(critical.some((h) => h.medical_needs.includes('dialysis'))).toBe(true);
  });

  it('has 6 teams mixing vehicles, skills and languages', () => {
    expect(teams).toHaveLength(6);
    expect(new Set(teams.map((t) => t.vehicle))).toEqual(
      new Set(['truck', 'flat_boat', 'kayak', 'on_foot']),
    );
    expect(new Set(teams.flatMap((t) => t.skills))).toEqual(
      new Set(['first_aid', 'boat_operator', 'swimmer']),
    );
    expect(new Set(teams.flatMap((t) => t.languages))).toEqual(
      new Set(['thai', 'english', 'burmese']),
    );
  });
});

describe('validators reject bad data', () => {
  it('rejects an unknown incident status', () => {
    const errors = validateIncident({ ...firstIncident, status: 'done' });
    expect(errors).toEqual([expect.stringContaining('.status:')]);
  });

  it('rejects a location outside Bangkok', () => {
    const errors = validateIncident({ ...firstIncident, location: { lat: 18.79, lon: 98.98 } });
    expect(errors).toEqual([expect.stringContaining('outside Bangkok bounds')]);
  });

  it('requires the original message for AI-extracted incidents', () => {
    const errors = validateIncident({ ...firstIncident, source: 'phone', original_message: null });
    expect(errors).toEqual([expect.stringContaining('required when ai_extracted is true')]);
  });

  it('rejects an unknown team skill and a missing field', () => {
    const { vehicle: _omit, ...noVehicle } = firstTeam;
    const errors = validateTeam({ ...noVehicle, skills: ['pilot'] });
    expect(errors).toHaveLength(2);
  });

  it('rejects a health record pointing at a missing incident', () => {
    const orphan = { ...health[0]!, incident_id: 'INC-999' };
    expect(validateHealth(orphan)).toEqual([]);
    expect(validateDataset({ incidents, health: [...health, orphan], teams })).toEqual([
      'health[INC-999]: incident_id not found in incidents',
    ]);
  });

  it('flags a medical need with no health record', () => {
    const errors = validateDataset({ incidents, health: health.slice(1), teams });
    expect(errors).toEqual([
      "incidents[INC-001]: has 'medical' need but no health record",
    ]);
  });

  it('does not put health values into error messages', () => {
    const bad = { ...health[0]!, priority: 'urgent' };
    const errors = validateHealth(bad).join(' ');
    expect(errors).not.toContain(health[0]!.notes);
    expect(errors).not.toContain('urgent');
  });
});
