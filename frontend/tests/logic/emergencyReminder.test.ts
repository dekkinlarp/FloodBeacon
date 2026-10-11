import { describe, expect, it } from 'vitest';
import { emergencyReminders } from '../../src/logic/emergencyReminder';

const kinds = (...args: Parameters<typeof emergencyReminders>) =>
  emergencyReminders(...args).map((r) => r.kind);

describe('emergencyReminders', () => {
  it('shows medical for a critical health record', () => {
    expect(kinds({ needs: ['medical'] }, { priority: 'critical' })).toEqual(['medical']);
  });

  it('does not show medical for non-critical or missing health records', () => {
    expect(kinds({ needs: ['medical'] }, { priority: 'high' })).toEqual([]);
    expect(kinds({ needs: ['medical'] }, undefined)).toEqual([]);
  });

  it('shows rescue when rescue is needed, alongside medical', () => {
    expect(kinds({ needs: ['rescue'] }, undefined)).toEqual(['rescue']);
    expect(kinds({ needs: ['medical', 'rescue'] }, { priority: 'critical' })).toEqual(['medical', 'rescue']);
  });

  it('tells the dispatcher what to call', () => {
    const labels = emergencyReminders({ needs: ['rescue'] }, { priority: 'critical' }).map((r) => r.label);
    expect(labels[0]).toMatch(/^Medical escalation/);
    expect(labels[1]).toMatch(/^Rescue escalation/);
  });
});
