import { describe, expect, it } from 'vitest';
import { contactBadge, formatHours, hoursSince } from '../../src/logic/contactBadge';

const now = new Date('2026-10-02T12:00:00+07:00');

describe('hoursSince', () => {
  it('counts hours across time zones', () => {
    expect(hoursSince('2026-10-02T03:00:00Z', now)).toBe(2); // 10:00 Bangkok
  });

  it('never goes negative for timestamps in the future', () => {
    expect(hoursSince('2026-10-02T13:00:00+07:00', now)).toBe(0);
  });
});

describe('formatHours', () => {
  it('shows <1h, then whole hours rounded down', () => {
    expect(formatHours(0.5)).toBe('<1h');
    expect(formatHours(5.9)).toBe('5h');
    expect(formatHours(30)).toBe('30h');
  });
});

describe('contactBadge', () => {
  const created_at = '2026-10-02T00:00:00+07:00';

  it('is not overdue at exactly 6 hours', () => {
    const b = contactBadge({ created_at, last_contact_at: '2026-10-02T06:00:00+07:00' }, now);
    expect(b).toEqual({ hours: 6, label: '6h', overdue: false });
  });

  it('is overdue after more than 6 hours', () => {
    const b = contactBadge({ created_at, last_contact_at: '2026-10-02T05:59:00+07:00' }, now);
    expect(b.overdue).toBe(true);
  });

  it('falls back to created_at when there is no last contact', () => {
    const b = contactBadge({ created_at, last_contact_at: null }, now);
    expect(b).toEqual({ hours: 12, label: '12h', overdue: true });
  });
});
