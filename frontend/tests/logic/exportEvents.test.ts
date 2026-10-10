import { describe, expect, it } from 'vitest';
import type { Event } from '../../src/types';
import { csvCell, eventsToCsv, eventsToJson, exportFileName } from '../../src/logic/exportEvents';

const e = (over: Partial<Event> = {}): Event => ({
  id: 'EVT-0001',
  occurred_at: '2026-10-02T01:30:00.000Z',
  actor: 'dispatcher',
  entity_type: 'incident',
  entity_id: 'INC-001',
  event_type: 'status_changed',
  from_value: 'verified',
  to_value: 'assigned',
  note: null,
  ...over,
});

describe('eventsToCsv', () => {
  it('writes a header and one row per event, nulls as empty cells', () => {
    expect(eventsToCsv([e()])).toBe(
      'id,occurred_at,actor,entity_type,entity_id,event_type,from_value,to_value,note\r\n' +
        'EVT-0001,2026-10-02T01:30:00.000Z,dispatcher,incident,INC-001,status_changed,verified,assigned,\r\n',
    );
  });

  it('writes only the header for an empty log', () => {
    expect(eventsToCsv([]).split('\r\n')).toEqual([
      'id,occurred_at,actor,entity_type,entity_id,event_type,from_value,to_value,note',
      '',
    ]);
  });

  it('quotes commas, quotes and line breaks', () => {
    expect(csvCell('a,b')).toBe('"a,b"');
    expect(csvCell('say "hi"')).toBe('"say ""hi"""');
    expect(csvCell('line1\nline2')).toBe('"line1\nline2"');
  });

  it('neutralises spreadsheet formulas', () => {
    expect(csvCell('=HYPERLINK("x")')).toBe(`"'=HYPERLINK(""x"")"`);
    expect(csvCell('+1')).toBe("'+1");
    expect(csvCell('@sum')).toBe("'@sum");
  });

  it('keeps Thai text and arrows as is', () => {
    expect(csvCell('TEAM-02 → INC-001')).toBe('TEAM-02 → INC-001');
    expect(csvCell('บางขุนเทียน')).toBe('บางขุนเทียน');
  });
});

describe('eventsToJson', () => {
  it('round-trips the events', () => {
    const events = [e(), e({ id: 'EVT-0002', note: 'x' })];
    expect(JSON.parse(eventsToJson(events))).toEqual(events);
  });
});

describe('exportFileName', () => {
  it('uses a file-system-safe UTC timestamp', () => {
    expect(exportFileName(new Date('2026-10-03T09:15:00.123Z'), 'csv')).toBe('dispatch-events-2026-10-03T09-15-00Z.csv');
  });
});
