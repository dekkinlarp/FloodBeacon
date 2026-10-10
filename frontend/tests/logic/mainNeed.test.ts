import { describe, expect, it } from 'vitest';
import { mainNeed } from '../../src/logic/mainNeed';

describe('mainNeed', () => {
  it('returns the first listed need', () => {
    expect(mainNeed({ needs: ['medical', 'evacuation'] })).toBe('medical');
  });

  it('returns null when there are no needs', () => {
    expect(mainNeed({ needs: [] })).toBeNull();
  });
});
