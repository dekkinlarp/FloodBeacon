import { describe, expect, it } from 'vitest';
import { emergencyReminders } from '../../src/logic/emergencyReminder';

const numbers = (...args: Parameters<typeof emergencyReminders>) =>
  emergencyReminders(...args).map((r) => r.number);

describe('emergencyReminders', () => {
  it('shows 1669 for a critical health record', () => {
    expect(numbers({ needs: ['medical'] }, { priority: 'critical' })).toEqual(['1669']);
  });

  it('does not show 1669 for non-critical or missing health records', () => {
    expect(numbers({ needs: ['medical'] }, { priority: 'high' })).toEqual([]);
    expect(numbers({ needs: ['medical'] }, undefined)).toEqual([]);
  });

  it('shows 1784 when rescue is needed, alongside 1669', () => {
    expect(numbers({ needs: ['rescue'] }, undefined)).toEqual(['1784']);
    expect(numbers({ needs: ['medical', 'rescue'] }, { priority: 'critical' })).toEqual(['1669', '1784']);
  });

  it('tells the dispatcher what to call', () => {
    const labels = emergencyReminders({ needs: ['rescue'] }, { priority: 'critical' }).map((r) => r.label);
    expect(labels[0]).toMatch(/^Call 1669/);
    expect(labels[1]).toMatch(/^Call 1784/);
  });
});
