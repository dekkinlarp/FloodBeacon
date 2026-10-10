import { describe, expect, it } from 'vitest';
import { RESOLVED_COLOUR, SEVERITY_COLOURS, markerStyle, severityRank } from '../../src/logic/severity';

describe('markerStyle', () => {
  it('colours by severity', () => {
    expect(markerStyle('critical', 'verified').fill).toBe(SEVERITY_COLOURS.critical);
    expect(markerStyle('high', 'new').fill).toBe(SEVERITY_COLOURS.high);
    expect(markerStyle('medium', 'assigned').fill).toBe(SEVERITY_COLOURS.medium);
    expect(markerStyle('low', 'on_scene').fill).toBe(SEVERITY_COLOURS.low);
  });

  it('greys out resolved incidents whatever the severity', () => {
    expect(markerStyle('critical', 'resolved').fill).toBe(RESOLVED_COLOUR);
  });

  it('uses dark ink on yellow and white ink elsewhere', () => {
    expect(markerStyle('medium', 'new').ink).toBe('#1a1a1a');
    expect(markerStyle('critical', 'new').ink).toBe('#ffffff');
  });
});

describe('severityRank', () => {
  it('orders critical < high < medium < low', () => {
    const ranks = (['critical', 'high', 'medium', 'low'] as const).map(severityRank);
    expect(ranks).toEqual([0, 1, 2, 3]);
  });
});
