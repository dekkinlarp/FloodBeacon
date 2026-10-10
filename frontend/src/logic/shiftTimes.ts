// Moves fake-data timestamps forward so they read as "recent" against the real
// clock. Relative gaps between all timestamps stay the same.

type Timestamped<K extends string> = { [P in K]: string | null };

export interface TimestampSet {
  records: readonly object[];
  fields: readonly string[];
}

function get(record: object, field: string): string | null {
  const v = (record as Record<string, unknown>)[field];
  return typeof v === 'string' ? v : null;
}

/** Latest timestamp (ms) across the given record fields, or null if none. */
export function latestTimestamp(sets: readonly TimestampSet[]): number | null {
  let latest: number | null = null;
  for (const { records, fields } of sets) {
    for (const r of records) {
      for (const f of fields) {
        const v = get(r, f);
        if (v !== null) latest = Math.max(latest ?? -Infinity, Date.parse(v));
      }
    }
  }
  return latest;
}

/** Returns copies of `records` with each listed field moved by `offsetMs`. Nulls stay null. */
export function shiftRecords<T extends Partial<Timestamped<K>>, K extends string>(
  records: readonly T[],
  fields: readonly K[],
  offsetMs: number,
): T[] {
  return records.map((r) => {
    const copy = { ...r };
    for (const f of fields) {
      const v = r[f];
      if (typeof v === 'string') {
        (copy as Record<string, unknown>)[f] = new Date(Date.parse(v) + offsetMs).toISOString();
      }
    }
    return copy;
  });
}

/** Offset that puts the latest timestamp `leadMs` before `now`. */
export function offsetToNow(latestMs: number, now: Date, leadMs: number): number {
  return now.getTime() - leadMs - latestMs;
}
