import { describe, expect, it } from 'vitest';
import catalog from '../../public/static/imagery/bridge-catalog/catalog.json';
import { loadFakeData } from '../../src/data/fakeData';
import { loadDemoScript } from '../../src/data/demoScript';
import { SITES, type SiteId } from '../../src/data/sites';
import { initialDispatchState } from '../../src/logic/dispatch';
import { runDueSteps } from '../../src/logic/demo';
import { validateDataset } from '../../src/logic/validateData';

const ids = Object.keys(SITES) as SiteId[];
const start = Date.parse('2026-10-10T12:00:00Z');

describe('satellite site exercises', () => {
  it.each(ids)('%s keeps synthetic locations in the matching imagery bounds and completes its script', siteId => {
    const data = loadFakeData({ siteId, shiftTo: new Date(start) });
    expect(validateDataset(data)).toEqual([]);
    expect(data.incidents).toHaveLength(20);
    expect(data.teams).toHaveLength(6);
    const bounds = catalog.cases.find(c => c.case.id === siteId)!.metadata.imagery.bounds;
    const script = loadDemoScript(siteId);
    const reported = script.steps.find(s => s.type === 'incident_reported');
    const locations = [
      ...data.incidents.map(i => i.location),
      ...data.teams.flatMap(t => [t.base_location, t.current_location]),
      ...(reported?.type === 'incident_reported' ? [reported.incident.location] : []),
    ];
    for (const point of locations) {
      expect(point.lon).toBeGreaterThanOrEqual(bounds[0]!);
      expect(point.lon).toBeLessThanOrEqual(bounds[2]!);
      expect(point.lat).toBeGreaterThanOrEqual(bounds[1]!);
      expect(point.lat).toBeLessThanOrEqual(bounds[3]!);
    }
    const result = runDueSteps(initialDispatchState(data), script, new Set(), start, start + 210 * 60_000);
    expect(result.log.filter(e => e.kind === 'skipped' && e.stepId !== 'S1')).toEqual([]);
    expect(result.state.incidents.find(i => i.id === 'INC-021')?.status).toBe('resolved');
    expect(result.state.feedback[0]?.people_helped).toBe(2);
  });

  it('selects distinct locations and reports for all three sites', () => {
    const datasets = ids.map(siteId => loadFakeData({ siteId }));
    expect(new Set(datasets.map(d => d.incidents[0]!.location.lon)).size).toBe(3);
    expect(new Set(datasets.map(d => d.incidents[0]!.district)).size).toBe(3);
    expect(new Set(datasets.map(d => d.teams[0]!.name)).size).toBe(3);
  });
});
