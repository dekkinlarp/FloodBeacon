import { describe, expect, it } from 'vitest';
import { changed } from '../../server/db';

describe('changed', () => {
  const key = (x: { id: string }) => x.id;

  it('returns new and modified records only', () => {
    const before = [{ id: 'a', v: 1 }, { id: 'b', v: 2 }];
    const after = [{ id: 'a', v: 1 }, { id: 'b', v: 3 }, { id: 'c', v: 4 }];
    expect(changed(before, after, key)).toEqual([{ id: 'b', v: 3 }, { id: 'c', v: 4 }]);
  });

  it('returns nothing when nothing changed', () => {
    const rows = [{ id: 'a', v: [1, 2] }];
    expect(changed(rows, structuredClone(rows), key)).toEqual([]);
  });
});
